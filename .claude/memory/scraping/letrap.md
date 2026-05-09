# Letra P (letrap.com.ar)

Aprendizajes específicos del scraping de letrap.com.ar.

---

## Estado actual

**Selectores usados:** genéricos (`a[href]` filtrado por longitud de texto y dominio).

**Volumen típico:** 50+ artículos detectados por carga, de los cuales ~7 quedan tras el filtro de relevancia y dedup.

**Calidad del material:** alto. Cubre bien política bonaerense, internas del PJ, rosca. Es la fuente más rica de las 3 que usamos.

## Pendiente

Optimizar con selectores específicos:

- Selector de notas en homepage (no genérico).
- Selector de título dentro de cada nota.
- Selector de copete / primer párrafo.
- Selector de imagen principal del artículo.

Para obtenerlos, abrir la home de letrap.com.ar con Claude en Chrome y navegar el DOM.

## Lo que funciona bien

- `og:image` está bien configurado en sus notas. La imagen extraída es la principal del artículo.
- Los titulares en home tienen entre 30 y 200 chars, fácil de filtrar por longitud.

## Lo que hay que mirar

- **Contenido R3 (rosca):** Letra P tiene mucho material de rosca pero algunos artículos son por suscripción o tienen el cuerpo cortado. Verificar que extraiga el cuerpo completo o al menos un copete sustancial.
- **Velocidad:** se cargan ads y trackers que ralentizan. Pendiente bloquear recursos pesados en el contexto del browser.
