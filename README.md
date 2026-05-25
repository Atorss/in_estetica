# in_estetica

Producto Odoo 18 para clínica de **Cirugía Plástica, Estética y Reconstructiva**.

Réplica de la base reutilizable de `in_nutricion`, con dominio clínico propio.
Single-tenant (una company por despliegue).

## Módulos

| Módulo | Rol |
|---|---|
| `innatum_ai` | Motor IA multi-proveedor (copia de terceros) |
| `muk_web_*` | Tema/UI backend (copia de terceros) |
| `in_estetica_control` | Suscripción + recargas IA + hard-expire (capa Innatum) |
| `in_estetica_core` | Roles + colaboradores *(pendiente)* |
| `in_estetica_agenda` | Tipos de cita + planificación + turnos *(pendiente)* |
| `in_estetica_web` | Sitio web + reserva online *(pendiente)* |
| `in_estetica_backend_theme` | Tema backend *(pendiente)* |

Ver `docs/ESTADO.md` para el detalle del avance.
