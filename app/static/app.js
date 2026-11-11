const STATUS = {
  aberta: "Aberta",
  em_analise: "Em análise",
  aguardando_peca: "Aguardando peça",
  concluida: "Concluída",
  cancelada: "Cancelada",
};

const TIPOS = {
  desktop: "Desktop",
  notebook: "Notebook",
  celular: "Celular",
  impressora: "Impressora",
  outro: "Outro",
};

const estado = {
  token: lerToken(),
  usuario: null,
  filtro: "",
  clientes: [],
  equipamentos: [],
};

const $ = (seletor) => document.querySelector(seletor);

function lerToken() {
  try {
    return localStorage.getItem("token");
  } catch {
    return null;
  }
}

function guardarToken(token) {
  estado.token = token;
  try {
    if (token) localStorage.setItem("token", token);
    else localStorage.removeItem("token");
  } catch {}
}

function el(tag, atributos = {}, ...filhos) {
  const elemento = document.createElement(tag);
  for (const [nome, valor] of Object.entries(atributos)) {
    if (nome === "class") elemento.className = valor;
    else if (nome.startsWith("on")) elemento.addEventListener(nome.slice(2), valor);
    else elemento.setAttribute(nome, valor);
  }
  for (const filho of filhos.flat()) {
    if (filho !== null && filho !== undefined && filho !== false) elemento.append(filho);
  }
  return elemento;
}

class ErroApi extends Error {
  constructor(status, detalhe, mensagem) {
    super(mensagem);
    this.status = status;
    this.detalhe = detalhe;
  }
}

function textoDoErro(status, detalhe) {
  if (typeof detalhe === "string") return detalhe;
  if (detalhe && detalhe.mensagem) return detalhe.mensagem;
  if (status === 422 && Array.isArray(detalhe)) {
    const campos = [...new Set(detalhe.map((d) => d.loc[d.loc.length - 1]))];
    return `Confira estes campos: ${campos.join(", ")}.`;
  }
  return "Algo deu errado. Tente de novo.";
}

async function api(caminho, { metodo = "GET", corpo } = {}) {
  const cabecalhos = {};
  if (corpo !== undefined) cabecalhos["Content-Type"] = "application/json";
  if (estado.token) cabecalhos.Authorization = `Bearer ${estado.token}`;

  const resposta = await fetch(caminho, {
    method: metodo,
    headers: cabecalhos,
    body: corpo === undefined ? undefined : JSON.stringify(corpo),
  });
  if (resposta.status === 204) return null;

  const dados = await resposta.json().catch(() => null);
  if (!resposta.ok) {
    const detalhe = dados && dados.detail;
    if (resposta.status === 401 && estado.usuario) {
      encerrarSessao();
      abrirLogin();
    }
    throw new ErroApi(resposta.status, detalhe, textoDoErro(resposta.status, detalhe));
  }
  return dados;
}

function formatarData(texto) {
  if (!texto) return "—";
  const data = new Date(texto.replace(" ", "T") + "Z");
  return data.toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

function formatarValor(valor) {
  if (valor === null || valor === undefined) return "—";
  return valor.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function badge(status) {
  const elemento = el("span", { class: "badge" }, STATUS[status] || status);
  elemento.style.setProperty("--cor", `var(--st-${status})`);
  return elemento;
}

function avisar(texto) {
  const aviso = $("#aviso");
  aviso.textContent = texto;
  aviso.hidden = false;
  clearTimeout(avisar.timer);
  avisar.timer = setTimeout(() => (aviso.hidden = true), 3500);
}

function mostrarErro(form, texto) {
  const caixa = form.querySelector(".erro");
  caixa.textContent = texto;
  caixa.hidden = !texto;
}

function dadosDoForm(form) {
  const dados = {};
  for (const [nome, valor] of new FormData(form)) {
    const limpo = valor.trim();
    if (limpo !== "") dados[nome] = limpo;
  }
  return dados;
}

function clientePorId(id) {
  return estado.clientes.find((c) => c.id === id);
}

function equipamentoPorId(id) {
  return estado.equipamentos.find((e) => e.id === id);
}

function descreverEquipamento(equipamento) {
  if (!equipamento) return "Equipamento removido";
  return `${TIPOS[equipamento.tipo]} ${equipamento.marca} ${equipamento.modelo}`;
}

function atualizarSessao() {
  const logado = Boolean(estado.usuario);
  $("#usuario-logado").hidden = !logado;
  $("#usuario-logado").textContent = logado ? `Olá, ${estado.usuario.usuario}` : "";
  $("#btn-entrar").hidden = logado;
  $("#btn-sair").hidden = !logado;
}

function encerrarSessao() {
  guardarToken(null);
  estado.usuario = null;
  atualizarSessao();
}

function abrirLogin() {
  const form = $("#form-login");
  form.reset();
  mostrarErro(form, "");
  if (!$("#dlg-login").open) $("#dlg-login").showModal();
}

function exigirLogin() {
  if (estado.usuario) return true;
  abrirLogin();
  return false;
}

async function carregarResumo() {
  const resumo = await api("/relatorios/resumo");
  const indicadores = Object.keys(STATUS).map((status) => {
    const cartao = el(
      "div",
      { class: "indicador" },
      el("span", {}, STATUS[status]),
      el("strong", {}, String(resumo.ordens_por_status[status] || 0)),
    );
    cartao.style.setProperty("--cor", `var(--st-${status})`);
    return cartao;
  });
  indicadores.push(
    el(
      "div",
      { class: "indicador faturado" },
      el("span", {}, "Faturado (concluídas)"),
      el("strong", {}, formatarValor(resumo.valor_concluidas)),
    ),
  );
  $("#resumo").replaceChildren(...indicadores);
}

function desenharFiltros() {
  const opcoes = [["", "Todas"], ...Object.entries(STATUS)];
  $("#filtros").replaceChildren(
    ...opcoes.map(([valor, rotulo]) =>
      el(
        "button",
        {
          class: valor === estado.filtro ? "chip ativo" : "chip",
          onclick: () => {
            estado.filtro = valor;
            desenharFiltros();
            carregarOrdens();
          },
        },
        rotulo,
      ),
    ),
  );
}

async function carregarOrdens() {
  const caminho = estado.filtro ? `/ordens?status=${estado.filtro}` : "/ordens";
  const ordens = await api(caminho);
  const linhas = ordens.map((ordem) => {
    const equipamento = equipamentoPorId(ordem.equipamento_id);
    const cliente = equipamento && clientePorId(equipamento.cliente_id);
    return el(
      "tr",
      { onclick: () => abrirOrdem(ordem.id) },
      el("td", {}, String(ordem.id)),
      el("td", {}, cliente ? cliente.nome : "—"),
      el("td", {}, descreverEquipamento(equipamento)),
      el("td", { class: "defeito", title: ordem.defeito_relatado }, ordem.defeito_relatado),
      el("td", {}, badge(ordem.status)),
      el("td", {}, formatarData(ordem.aberta_em)),
    );
  });
  $("#lista-ordens").replaceChildren(...linhas);
  $("#ordens-vazio").hidden = ordens.length > 0;
}

async function carregarCadastros() {
  [estado.clientes, estado.equipamentos] = await Promise.all([api("/clientes"), api("/equipamentos")]);

  $("#form-equipamento [name=cliente_id]").replaceChildren(
    ...estado.clientes.map((c) => el("option", { value: c.id }, c.nome)),
  );

  $("#form-ordem [name=equipamento_id]").replaceChildren(
    ...estado.equipamentos.map((e) => {
      const cliente = clientePorId(e.cliente_id);
      return el("option", { value: e.id }, `${descreverEquipamento(e)} — ${cliente ? cliente.nome : "?"}`);
    }),
  );

  $("#lista-clientes").replaceChildren(
    ...estado.clientes.map((cliente) => {
      const equipamentos = estado.equipamentos.filter((e) => e.cliente_id === cliente.id);
      return el(
        "article",
        { class: "cliente" },
        el("strong", {}, cliente.nome),
        el("span", { class: "sub" }, [cliente.telefone, cliente.email].filter(Boolean).join(" · ")),
        equipamentos.length
          ? el("ul", {}, equipamentos.map((e) => el("li", {}, descreverEquipamento(e))))
          : el("span", { class: "sub" }, "Nenhum equipamento cadastrado"),
      );
    }),
  );
}

async function carregarTudo() {
  try {
    await carregarCadastros();
    await Promise.all([carregarOrdens(), carregarResumo()]);
  } catch (erro) {
    avisar(erro.message);
  }
}

function explicarTransicao(detalhe) {
  const permitidos = detalhe.permitidos.map((s) => STATUS[s]);
  const atual = STATUS[detalhe.status_atual];
  if (!permitidos.length) return `Uma ordem ${atual.toLowerCase()} está encerrada e não muda mais de status.`;
  return `Essa mudança não é permitida. Uma ordem "${atual}" só pode ir para: ${permitidos.join(" ou ")}.`;
}

function desenharOrdem(ordem) {
  const equipamento = equipamentoPorId(ordem.equipamento_id);
  const cliente = equipamento && clientePorId(equipamento.cliente_id);
  const encerrada = ordem.status === "concluida" || ordem.status === "cancelada";

  const formEdicao = el(
    "form",
    { class: "linha-form" },
    el("label", {}, "Diagnóstico", el("input", { name: "diagnostico", maxlength: "1000" })),
    el("label", {}, "Valor (R$)", el("input", { name: "valor", type: "number", min: "0", step: "0.01" })),
    el("button", { class: "btn" }, "Salvar"),
    el("p", { class: "erro", hidden: "" }),
  );
  formEdicao.diagnostico.value = ordem.diagnostico || "";
  formEdicao.valor.value = ordem.valor ?? "";
  formEdicao.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    if (!exigirLogin()) return;
    const corpo = { diagnostico: formEdicao.diagnostico.value.trim() || null };
    corpo.valor = formEdicao.valor.value === "" ? null : Number(formEdicao.valor.value);
    try {
      desenharOrdem(await api(`/ordens/${ordem.id}`, { metodo: "PATCH", corpo }));
      avisar("Ordem atualizada.");
      carregarTudo();
    } catch (erro) {
      mostrarErro(formEdicao, erro.message);
    }
  });

  const formStatus = el(
    "form",
    { class: "linha-form" },
    el(
      "label",
      {},
      "Novo status",
      el(
        "select",
        { name: "status" },
        Object.entries(STATUS)
          .filter(([valor]) => valor !== ordem.status)
          .map(([valor, rotulo]) => el("option", { value: valor }, rotulo)),
      ),
    ),
    el("button", { class: "btn" }, "Mudar status"),
    el("p", { class: "erro", hidden: "" }),
  );
  formStatus.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    if (!exigirLogin()) return;
    try {
      const atualizada = await api(`/ordens/${ordem.id}/status`, {
        metodo: "PATCH",
        corpo: { status: formStatus.status.value },
      });
      desenharOrdem(atualizada);
      avisar(`Status alterado para ${STATUS[atualizada.status]}.`);
      carregarTudo();
    } catch (erro) {
      const texto = erro.status === 409 && erro.detalhe && erro.detalhe.permitidos
        ? explicarTransicao(erro.detalhe)
        : erro.message;
      mostrarErro(formStatus, texto);
    }
  });

  $("#detalhe-ordem").replaceChildren(
    el(
      "div",
      { class: "cabecalho-ordem" },
      el("h2", {}, `Ordem #${ordem.id}`),
      badge(ordem.status),
    ),
    el(
      "dl",
      { class: "dados" },
      el("dt", {}, "Cliente"),
      el("dd", {}, cliente ? `${cliente.nome} · ${cliente.telefone}` : "—"),
      el("dt", {}, "Equipamento"),
      el("dd", {}, descreverEquipamento(equipamento)),
      el("dt", {}, "Defeito relatado"),
      el("dd", {}, ordem.defeito_relatado),
      el("dt", {}, "Diagnóstico"),
      el("dd", {}, ordem.diagnostico || "—"),
      el("dt", {}, "Valor"),
      el("dd", {}, formatarValor(ordem.valor)),
      el("dt", {}, "Aberta em"),
      el("dd", {}, formatarData(ordem.aberta_em)),
      el("dt", {}, "Concluída em"),
      el("dd", {}, formatarData(ordem.concluida_em)),
    ),
    encerrada
      ? el("p", { class: "dica" }, "Esta ordem está encerrada: diagnóstico, valor e status não mudam mais.")
      : el("div", { class: "bloco" }, el("h3", {}, "Diagnóstico e valor"), formEdicao),
    encerrada ? null : el("div", { class: "bloco" }, el("h3", {}, "Status"), formStatus),
    el(
      "div",
      { class: "bloco" },
      el("h3", {}, "Histórico"),
      el(
        "ul",
        { class: "historico" },
        ordem.historico.map((h) =>
          el(
            "li",
            {},
            el(
              "span",
              {},
              h.status_anterior ? `${STATUS[h.status_anterior]} → ${STATUS[h.status_novo]}` : `Aberta`,
            ),
            el("span", { class: "sub" }, formatarData(h.alterado_em)),
          ),
        ),
      ),
    ),
    el(
      "div",
      { class: "acoes" },
      el("button", { class: "btn btn-leve", onclick: () => $("#dlg-ordem").close() }, "Fechar"),
    ),
  );
}

async function abrirOrdem(id) {
  try {
    desenharOrdem(await api(`/ordens/${id}`));
    if (!$("#dlg-ordem").open) $("#dlg-ordem").showModal();
  } catch (erro) {
    avisar(erro.message);
  }
}

function ligarFormulario(seletor, enviar) {
  const form = $(seletor);
  form.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    mostrarErro(form, "");
    try {
      await enviar(form);
    } catch (erro) {
      mostrarErro(form, erro.message);
    }
  });
}

ligarFormulario("#form-login", async (form) => {
  const { token } = await api("/login", { metodo: "POST", corpo: dadosDoForm(form) });
  guardarToken(token);
  estado.usuario = await api("/me");
  atualizarSessao();
  $("#dlg-login").close();
  avisar(`Bem-vindo, ${estado.usuario.usuario}.`);
});

ligarFormulario("#form-cliente", async (form) => {
  if (!exigirLogin()) return;
  const cliente = await api("/clientes", { metodo: "POST", corpo: dadosDoForm(form) });
  form.reset();
  avisar(`Cliente ${cliente.nome} cadastrado.`);
  await carregarTudo();
});

ligarFormulario("#form-equipamento", async (form) => {
  if (!exigirLogin()) return;
  const dados = dadosDoForm(form);
  dados.cliente_id = Number(dados.cliente_id);
  await api("/equipamentos", { metodo: "POST", corpo: dados });
  form.reset();
  avisar("Equipamento cadastrado.");
  await carregarTudo();
});

ligarFormulario("#form-ordem", async (form) => {
  const dados = dadosDoForm(form);
  dados.equipamento_id = Number(dados.equipamento_id);
  const ordem = await api("/ordens", { metodo: "POST", corpo: dados });
  form.reset();
  $("#dlg-nova-ordem").close();
  avisar(`Ordem #${ordem.id} aberta.`);
  await carregarTudo();
});

$("#btn-nova-ordem").addEventListener("click", () => {
  if (!exigirLogin()) return;
  mostrarErro($("#form-ordem"), "");
  $("#dlg-nova-ordem").showModal();
});

$("#btn-entrar").addEventListener("click", abrirLogin);

$("#btn-sair").addEventListener("click", async () => {
  try {
    await api("/logout", { metodo: "POST" });
  } catch {}
  encerrarSessao();
  avisar("Você saiu.");
});

document.querySelectorAll("[data-fechar]").forEach((botao) => {
  botao.addEventListener("click", () => botao.closest("dialog").close());
});

document.querySelectorAll(".aba").forEach((aba) => {
  aba.addEventListener("click", () => {
    document.querySelectorAll(".aba").forEach((a) => a.classList.toggle("ativa", a === aba));
    $("#aba-ordens").hidden = aba.dataset.aba !== "ordens";
    $("#aba-clientes").hidden = aba.dataset.aba !== "clientes";
  });
});

async function iniciar() {
  desenharFiltros();
  if (estado.token) {
    try {
      estado.usuario = await api("/me");
    } catch {
      encerrarSessao();
    }
  }
  atualizarSessao();
  await carregarTudo();
}

iniciar();
