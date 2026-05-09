# La Tecla (latecla.info)

Aprendizajes específicos del scraping de latecla.info.

---

## Estado actual

**Selectores usados:** genéricos (igual que Letra P).

**Volumen típico:** ~30 artículos detectados, ~5-7 quedan tras el filtro de relevancia.

**Calidad del material:** bueno para política bonaerense y temas legislativos. Cubre Senado y Cámara de Diputados con frecuencia.

## Pendiente

Optimizar con selectores específicos del DOM de latecla.info.

## Lo que funciona bien

- Cobertura fuerte de Legislatura — útil para balancear esa categoría que históricamente tenía poca representación.
- `og:image` bien configurado.

## Lo que hay que mirar

- A veces tira artículos antiguos en home si tuvo poca actividad reciente. El filtro de relevancia por palabras clave ayuda pero no descarta por fecha. Si esto se vuelve un problema, agregar filtro de fecha en el HTML del artículo.
