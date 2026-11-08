/* Melbourne Empleo — lógica del frontend. Sin dependencias. */
(() => {
  "use strict";

  const CLAVE_PERFIL = "melbourne-empleo:perfil:v1";
  const ORIGEN_ACTUAL = (window.location && window.location.origin && window.location.origin.startsWith("http")) ? window.location.origin : "";
  const API_LOCAL = ((window.CONFIG && window.CONFIG.API_LOCAL) || (ORIGEN_ACTUAL.includes("8787") ? ORIGEN_ACTUAL : "")).replace(/\/+$/, "");
  const DEMO = window.DEMO || { ofertas: [], total: 0 };

  const CAMPOS = [
    "visa",
    "derecho_a_trabajar",
    "horas_disponibles",
    "disponibilidad",
    "certificaciones",
    "nivel_de_ingles",
    "experiencia",
    "salario_minimo",
    "viaje_maximo_minutos",
  ];

  const LIMPIEZA = [
    "cleaner",
    "cleaning",
    "housekeep",
    "janitor",
    "limpieza",
    "domestic clean",
    "commercial clean",
    "window clean",
    "laundry attendant",
  ];

  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => Array.from(document.querySelectorAll(sel));

  const estado = {
    perfil: {},
    ofertas: [],
    cargando: false,
    modo: "demo",
  };

  /* ── Utilidades ─────────────────────────────────────────────── */

  function normalizar(texto) {
    return String(texto || "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .trim();
  }

  function escapar(texto) {
    return String(texto == null ? "" : texto)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function estaVacio(valor) {
    const limpio = normalizar(valor);
    return !limpio || limpio === "completar" || limpio === "no especificado" || limpio === "pendiente";
  }

  function faltantes() {
    return CAMPOS.filter((campo) => estaVacio(estado.perfil[campo]));
  }

  function cargarPerfil() {
    let guardado = {};
    try {
      guardado = JSON.parse(localStorage.getItem(CLAVE_PERFIL) || "{}") || {};
    } catch {
      guardado = {};
    }
    estado.perfil = { nivel_de_ingles: "intermedio", ...guardado };
  }

  function guardarPerfil(perfil) {
    estado.perfil = { ...estado.perfil, ...perfil };
    try {
      localStorage.setItem(CLAVE_PERFIL, JSON.stringify(estado.perfil));
    } catch {
      /* modo privado: seguimos en memoria */
    }
    actualizarPerfilUI();
  }

  function toast(mensaje) {
    const nodo = $("#toast");
    nodo.textContent = mensaje;
    nodo.hidden = false;
    clearTimeout(toast.temporizador);
    toast.temporizador = setTimeout(() => {
      nodo.hidden = true;
    }, 3200);
  }

  function textoPublicada(oferta) {
    const crudo = String(oferta.publicada_texto || "").trim();
    const coincidencia = crudo.match(/(\d+)\s*([dhm])/i);
    if (!coincidencia) return crudo || "fecha no indicada";
    const cantidad = Number(coincidencia[1]);
    const unidad = coincidencia[2].toLowerCase();
    const etiqueta = unidad === "d" ? (cantidad === 1 ? "día" : "días") : unidad === "h" ? (cantidad === 1 ? "hora" : "horas") : "min";
    return `hace ${cantidad} ${etiqueta}`;
  }

  function claseJornada(jornada) {
    const valor = normalizar(jornada);
    if (valor.includes("part")) return "parcial";
    if (valor.includes("casual")) return "casual";
    return "";
  }

  function etiquetaJornada(jornada) {
    const valor = normalizar(jornada);
    if (valor.includes("full")) return "Jornada completa";
    if (valor.includes("part")) return "Medio tiempo";
    if (valor.includes("casual")) return "Casual";
    if (valor.includes("contract")) return "Contrato temporal";
    return jornada || "Jornada no indicada";
  }

  /* ── Perfil: hero, aviso y diálogo ──────────────────────────── */

  function actualizarPerfilUI() {
    const falta = faltantes();

    $("#dato-visa").textContent = estaVacio(estado.perfil.visa)
      ? "Visa por completar"
      : estado.perfil.visa;
    $("#dato-horas").textContent = estaVacio(estado.perfil.horas_disponibles)
      ? "Horas por definir"
      : `${estado.perfil.horas_disponibles} h/semana`;
    $("#dato-zona").textContent = estaVacio(estado.perfil.viaje_maximo_minutos)
      ? "Melbourne"
      : `Melbourne · hasta ${estado.perfil.viaje_maximo_minutos} min`;

    $("#perfil-punto").hidden = falta.length === 0;

    const aviso = $("#aviso-perfil");
    if (falta.length === 0) {
      aviso.hidden = true;
      return;
    }
    aviso.hidden = false;
    const nombres = falta.map((campo) => campo.replace(/_/g, " "));
    $("#aviso-texto").textContent =
      `Falta${falta.length === 1 ? "" : "n"} ${falta.length} dato${falta.length === 1 ? "" : "s"}: ` +
      nombres.slice(0, 4).join(", ") +
      (nombres.length > 4 ? "…" : "") +
      ". Sin ellos no se descarta ninguna oferta: se marca «verificar».";
  }

  function abrirPerfil() {
    const form = $("#form-perfil");
    CAMPOS.forEach((campo) => {
      const control = form.elements.namedItem(campo);
      if (control) control.value = estado.perfil[campo] || "";
    });
    $("#dialogo-perfil").showModal();
  }

  function enlazarPerfil() {
    $("#abrir-perfil").addEventListener("click", abrirPerfil);
    $$("[data-abrir-perfil]").forEach((nodo) => nodo.addEventListener("click", abrirPerfil));
    $("#cerrar-perfil").addEventListener("click", () => $("#dialogo-perfil").close());

    const dialogo = $("#dialogo-perfil");
    dialogo.addEventListener("click", (evento) => {
      if (evento.target === dialogo) dialogo.close();
    });

    $("#form-perfil").addEventListener("submit", (evento) => {
      evento.preventDefault();
      const datos = {};
      CAMPOS.forEach((campo) => {
        const control = evento.target.elements.namedItem(campo);
        if (control) datos[campo] = control.value.trim();
      });
      guardarPerfil(datos);
      dialogo.close();
      toast("Perfil guardado en este navegador");
    });

    $("#limpiar-perfil").addEventListener("click", () => {
      if (!confirm("¿Borrar los datos del perfil guardados en este navegador?")) return;
      try {
        localStorage.removeItem(CLAVE_PERFIL);
      } catch {
        /* nada */
      }
      estado.perfil = { nivel_de_ingles: "intermedio" };
      $("#form-perfil").reset();
      actualizarPerfilUI();
      toast("Perfil borrado");
    });
  }

  /* ── Búsqueda ───────────────────────────────────────────────── */

  function filtrarDemo(cuerpo) {
    const terminos = normalizar(cuerpo.keywords).split(/\s+/).filter(Boolean);
    const jornada = normalizar(cuerpo.jornada || "fulltime");

    let excluidas = 0;
    const ofertas = (DEMO.ofertas || []).filter((oferta) => {
      const titulo = normalizar(oferta.titulo);
      if (LIMPIEZA.some((palabra) => titulo.includes(palabra))) {
        excluidas += 1;
        return false;
      }
      if (jornada !== "cualquiera") {
        const tipo = normalizar(oferta.jornada);
        const esperado = { fulltime: "full", parttime: "part", casual: "casual", contract: "contract" }[jornada];
        if (esperado && !tipo.includes(esperado)) return false;
      }
      if (terminos.length) {
        const heno = normalizar(
          `${oferta.titulo} ${oferta.empresa} ${oferta.categoria} ${oferta.resumen}`
        );
        if (!terminos.every((termino) => heno.includes(termino))) return false;
      }
      return true;
    });

    return {
      modo: "demo",
      fuente: "SEEK",
      total_en_portal: DEMO.total,
      devueltas: ofertas.length,
      excluidas_por_limpieza: Array.from({ length: excluidas }, () => ({})),
      ofertas,
      permite_ia: false,
    };
  }

  async function pedir(url, cuerpo, esperaMs) {
    const controlador = new AbortController();
    const temporizador = setTimeout(() => controlador.abort(), esperaMs || 25000);
    try {
      const respuesta = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(cuerpo),
        signal: controlador.signal,
      });
      if (!respuesta.ok) throw new Error(`HTTP ${respuesta.status}`);
      return await respuesta.json();
    } finally {
      clearTimeout(temporizador);
    }
  }

  async function buscar(keywords, jornada) {
    if (estado.cargando) return;
    estado.cargando = true;
    const boton = $("#btn-buscar");
    boton.disabled = true;
    $("#vacio").hidden = true;
    $("#estado").hidden = false;
    $("#estado-texto").textContent = API_LOCAL
      ? "Consultando tu agente local…"
      : "Consultando SEEK…";
    $("#ofertas").innerHTML = "";
    $("#meta").innerHTML = "";

    const cuerpo = { keywords, jornada, paginas: 1, perfil: estado.perfil };

    try {
      let datos;
      if (API_LOCAL) {
        datos = await pedir(`${API_LOCAL}/buscar`, cuerpo, 30000);
      } else {
        try {
          datos = await pedir("/api/buscar", cuerpo, 25000);
        } catch {
          datos = filtrarDemo(cuerpo);
        }
      }
      estado.modo = datos.modo || "demo";
      estado.ofertas = datos.ofertas || [];
      renderizar(datos);
    } catch (error) {
      $("#vacio").hidden = false;
      $("#vacio").querySelector("h3").textContent = "No pude consultar la fuente";
      $("#vacio").querySelector("p").textContent =
        "Revisa tu conexión o vuelve a intentarlo. Detalle: " + error.message;
    } finally {
      estado.cargando = false;
      boton.disabled = false;
      $("#estado").hidden = true;
    }
  }

  function renderizar(datos) {
    const ofertas = datos.ofertas || [];
    const excluidas = (datos.excluidas_por_limpieza || []).length;
    const modo = datos.modo || "demo";

    const etiquetaModo =
      modo === "local" ? "agente local" : modo === "ia" ? "informe IA" : "demostración";
    $("#pie-modo").textContent =
      modo === "local" ? "Conectado a tu agente local" : modo === "ia" ? "Informe generado por IA" : "Modo demostración";

    const partes = [
      `<b>${ofertas.length}</b> oferta${ofertas.length === 1 ? "" : "s"}`,
      `<span class="pildora">${escapar(datos.fuente || "SEEK")}</span>`,
      `<span class="pildora neutra">${etiquetaModo}</span>`,
    ];
    if (excluidas) {
      partes.push(`<span class="pildora rosa">${excluidas} de limpieza excluida${excluidas === 1 ? "" : "s"}</span>`);
    }
    if (datos.total_en_portal) {
      partes.push(`<span>de ${Number(datos.total_en_portal).toLocaleString("es-AU")} en el portal</span>`);
    }
    if (datos.aviso) {
      partes.push(`<span title="${escapar(datos.aviso)}">⚠️ ${escapar(datos.aviso)}</span>`);
    }

    const meta = $("#meta");
    meta.innerHTML = partes.join('<span class="punto-sep" aria-hidden="true">·</span>');

    if (datos.permite_ia) {
      const boton = document.createElement("button");
      boton.className = "btn btn-mini";
      boton.type = "button";
      boton.textContent = "Pedir informe al agente (IA)";
      boton.addEventListener("click", pedirInforme);
      meta.appendChild(boton);
    }

    const contenedor = $("#ofertas");
    contenedor.innerHTML = "";

    if (!ofertas.length) {
      $("#vacio").hidden = false;
      return;
    }
    $("#vacio").hidden = true;

    ofertas.forEach((oferta, indice) => {
      contenedor.appendChild(crearTarjeta(oferta, indice));
    });
  }

  function crearTarjeta(oferta, indice) {
    const articulo = document.createElement("article");
    articulo.className = "card";
    articulo.style.animationDelay = `${Math.min(indice * 35, 350)}ms`;

    const salario = estaVacio(oferta.salario) ? "Salario no especificado" : oferta.salario;
    const visa = estaVacio(estado.perfil.visa) ? "Verificar derecho a trabajar" : "";

    articulo.innerHTML = `
      <div class="card-top">
        <span class="badge ${claseJornada(oferta.jornada)}">${escapar(etiquetaJornada(oferta.jornada))}</span>
        <span class="badge" style="background:#eef2ff;color:#3730a3;border:1px solid #c7d2fe;font-size:0.75rem;">${escapar(oferta.fuente || "SEEK")}</span>
        <span class="card-fecha">${escapar(textoPublicada(oferta))}</span>
      </div>
      <h3><a href="${escapar(oferta.enlace)}" target="_blank" rel="noopener noreferrer">${escapar(oferta.titulo)}</a></h3>
      <p class="empresa">${escapar(oferta.empresa || "Empresa no especificada")}</p>
      <ul class="detalles">
        <li><span class="ico" aria-hidden="true">📍</span><span>${escapar(oferta.ubicacion || "Ubicación no indicada")}</span></li>
        <li><span class="ico" aria-hidden="true">💰</span><span>${escapar(salario)}</span></li>
        <li><span class="ico" aria-hidden="true">🗂️</span><span>${escapar(oferta.categoria || "Categoría no indicada")}</span></li>
      </ul>
      ${oferta.resumen ? `<p class="resumen-oferta">${escapar(oferta.resumen)}</p>` : ""}
      <div class="card-foot">
        <span class="aviso-visa">${escapar(visa)}</span>
        <a class="enlace-oferta" href="${escapar(oferta.enlace)}" target="_blank" rel="noopener noreferrer">Ver oferta ↗</a>
      </div>
    `;
    return articulo;
  }

  /* ── Informe de IA (solo con servidor local) ────────────────── */

  async function pedirInforme() {
    if (!API_LOCAL) return;
    const acepta = confirm(
      "El agente usará el modelo de Claude y puede costar hasta US$0.30 por corrida. ¿Continuar?"
    );
    if (!acepta) return;

    $("#estado").hidden = false;
    $("#estado-texto").textContent = "El agente está trabajando… puede tardar un minuto.";
    try {
      const datos = await pedir(`${API_LOCAL}/informe`, { perfil: estado.perfil }, 300000);
      mostrarInforme(datos.informe || "El agente no devolvió texto.");
    } catch (error) {
      toast("No pude generar el informe: " + error.message);
    } finally {
      $("#estado").hidden = true;
    }
  }

  function mostrarInforme(markdown) {
    const cuerpo = $("#informe-cuerpo");
    cuerpo.innerHTML = markdownMinimo(markdown);
    $("#informe").hidden = false;
    $("#informe").scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function markdownMinimo(texto) {
    const lineas = String(texto).split(/\r?\n/);
    const salida = [];
    let enLista = false;

    const enLinea = (valor) =>
      escapar(valor)
        .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
        .replace(/\[(.+?)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')
        .replace(/(^|[\s(])(https?:\/\/[^\s<)]+)/g, '$1<a href="$2" target="_blank" rel="noopener noreferrer">$2</a>');

    lineas.forEach((linea) => {
      const limpia = linea.trim();
      if (!limpia) {
        if (enLista) {
          salida.push("</ul>");
          enLista = false;
        }
        return;
      }
      if (limpia.startsWith("### ")) {
        if (enLista) { salida.push("</ul>"); enLista = false; }
        salida.push(`<h3>${enLinea(limpia.slice(4))}</h3>`);
      } else if (limpia.startsWith("## ")) {
        if (enLista) { salida.push("</ul>"); enLista = false; }
        salida.push(`<h2>${enLinea(limpia.slice(3))}</h2>`);
      } else if (limpia.startsWith("# ")) {
        if (enLista) { salida.push("</ul>"); enLista = false; }
        salida.push(`<h2>${enLinea(limpia.slice(2))}</h2>`);
      } else if (limpia.startsWith("- ")) {
        if (!enLista) { salida.push("<ul>"); enLista = true; }
        salida.push(`<li>${enLinea(limpia.slice(2))}</li>`);
      } else {
        if (enLista) { salida.push("</ul>"); enLista = false; }
        salida.push(`<p>${enLinea(limpia)}</p>`);
      }
    });
    if (enLista) salida.push("</ul>");
    return salida.join("\n");
  }

  /* ── Enlaces de la interfaz ─────────────────────────────────── */

  function enlazarBuscador() {
    const form = $("#form-buscar");
    form.addEventListener("submit", (evento) => {
      evento.preventDefault();
      buscar($("#q").value.trim(), $("#jornada").value);
    });

    $$(".chip").forEach((chip) => {
      chip.addEventListener("click", () => {
        const consulta = chip.dataset.q || "";
        const activo = chip.getAttribute("aria-pressed") === "true";
        $$(".chip").forEach((otro) => otro.setAttribute("aria-pressed", "false"));
        if (activo) {
          $("#q").value = "";
        } else {
          chip.setAttribute("aria-pressed", "true");
          $("#q").value = consulta;
        }
        buscar($("#q").value.trim(), $("#jornada").value);
      });
    });

    $("#jornada").addEventListener("change", () => {
      buscar($("#q").value.trim(), $("#jornada").value);
    });

    $("#cerrar-informe").addEventListener("click", () => {
      $("#informe").hidden = true;
    });
  }

  /* ── Arranque ───────────────────────────────────────────────── */

  function iniciar() {
    cargarPerfil();
    actualizarPerfilUI();
    enlazarPerfil();
    enlazarBuscador();

    // Primera carga: mostramos las ofertas más recientes sin exigir clic.
    estado.ofertas = (DEMO.ofertas || []).slice(0, 12);
    if (estado.ofertas.length) {
      renderizar({
        modo: "demo",
        fuente: "SEEK",
        total_en_portal: DEMO.total,
        ofertas: estado.ofertas,
        excluidas_por_limpieza: [],
        permite_ia: false,
      });
      $("#meta").insertAdjacentHTML(
        "afterbegin",
        '<span>Vista previa · pulsa <b>Buscar</b> para consultar en vivo</span><span class="punto-sep" aria-hidden="true">·</span>'
      );
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", iniciar);
  } else {
    iniciar();
  }
})();
