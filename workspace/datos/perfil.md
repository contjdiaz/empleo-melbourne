# Perfil de la usuaria

> **Este es el único archivo que tienes que editar.**
> Rellena la ficha de abajo y guarda. El agente lee esos valores antes de buscar.
> Si dejas `COMPLETAR`, el agente no lo inventa: marca la oferta como
> «confirmar» y te dice exactamente qué dato le falta.

## Ficha para diligenciar

Escribe el valor después de los dos puntos. No borres la palabra clave.

```text
visa: COMPLETAR
derecho_a_trabajar: COMPLETAR
horas_disponibles: COMPLETAR
disponibilidad: COMPLETAR
certificaciones: COMPLETAR
nivel_de_ingles: intermedio
experiencia: COMPLETAR
salario_minimo: COMPLETAR
zona: Melbourne y alrededores con transporte público razonable
viaje_maximo_minutos: COMPLETAR
```

### Qué poner en cada campo

| Campo | Qué escribir | Ejemplo |
|---|---|---|
| `visa` | El nombre y número de tu visa. | `Student visa (subclass 500)` |
| `derecho_a_trabajar` | Cuántas horas y con qué límites te permite trabajar. | `24 h/semana durante el curso, sin límite en vacaciones` |
| `horas_disponibles` | Cuántas horas por semana puedes trabajar de verdad. | `38` |
| `disponibilidad` | Días y franjas en que puedes trabajar. | `lunes a viernes, mañana y tarde; sábados` |
| `certificaciones` | Cursos o licencias australianas que ya tienes. | `RSA, First Aid` o `ninguna` |
| `nivel_de_ingles` | Ya está puesto; cámbialo si mejora. | `intermedio` |
| `experiencia` | Áreas y años de experiencia laboral. | `atención al cliente, 3 años; administración, 1 año` |
| `salario_minimo` | Lo mínimo que aceptarías, por hora o por año. | `$30/hora` |
| `viaje_maximo_minutos` | Cuánto estás dispuesta a viajar. | `60` |

### Si no sabes qué visa tienes

Tu visa y sus condiciones se consultan gratis y oficialmente en **VEVO**, con
tu pasaporte o número de referencia de visa:

<https://immi.homeaffairs.gov.au/visas/already-have-a-visa/check-visa-details-and-conditions/check-conditions-online>

Ese dato es el que más cambia la búsqueda: define cuántas horas puedes aceptar
y qué ofertas te son legalmente posibles. No lo dejes en `COMPLETAR` por mucho
tiempo.

## Contexto fijo

- Origen: Colombia. Vive en Melbourne, Australia.
- Lleva dos años estudiando inglés y sigue mejorando.
- No ha conseguido un trabajo estable; busca uno.
- Objetivo: empleo estable, con la mayor cantidad de horas semanales posible.
- Preferencia: jornada completa o contrato permanente; acepta parcial si suma horas.
- **Exclusión explícita: nada de limpieza** (`cleaner`, `cleaning`, `housekeeping`).
- Solo ofertas en Melbourne y alrededores con transporte público razonable.

## Cómo usa el agente este archivo

1. Lee la ficha y comprueba qué campos quedaron en `COMPLETAR`.
2. Si `visa` o `derecho_a_trabajar` faltan, **no descarta** ofertas: las marca
   como «verificar derecho a trabajar» para que tú decidas.
3. Si `horas_disponibles` falta, ordena por horas y no filtra por elegibilidad.
4. Nunca agrega datos personales que no estén aquí.

Para ver qué falta sin gastar tokens:

```bash
uv run python -m proveedores.perfil
```
