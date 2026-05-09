# Infocielo (infocielo.com)

Aprendizajes específicos del scraping de infocielo.com.

---

## Estado actual

**Selectores usados:** genéricos (igual que los otros portales).

**Volumen típico:** ~20 artículos detectados, ~3-5 quedan tras el filtro de relevancia.

**Calidad del material:** medio. Mezcla política bonaerense con cobertura general. La parte política es buena pero hay que filtrar más.

## Pendiente

Optimizar con selectores específicos del DOM de infocielo.com.

## Lo que hay que mirar

### URLs relativas en imágenes

Algunos `<img src>` de Infocielo vienen como rutas relativas (ej: `/upload/imagen/foto.jpg` en vez de `https://infocielo.com/upload/imagen/foto.jpg`). Cuando se intenta usar como URL de imagen, falla.

**Solución:** resolver contra el dominio base si la URL no empieza con `http`.

```python
if src and not src.startswith("http"):
    src = "https://infocielo.com" + src
```

(No verificado si está implementado actualmente. Revisar `scraper.py` función `extraer_og_image`.)

### Endpoint de redimensionado

Algunas URLs de imagen son endpoints internos tipo `infobae.com/new-resizer/...` (que también afectan a otros portales que usan el mismo CMS). Estos endpoints requieren parámetros firmados que no son públicos. Si encontramos imágenes así, descartar y buscar otra.
