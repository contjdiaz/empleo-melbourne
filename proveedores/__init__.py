"""Proveedores de ofertas de empleo.

Cada módulo expone `buscar(...)` y devuelve un dict con `ofertas`, `excluidas`
y metadatos de la consulta. El agente los usa a través de herramientas MCP.

El import se hace explícito (`from proveedores import seek`) para que
`python -m proveedores.seek` no dispare avisos de importación doble.
"""

__all__: list[str] = []
