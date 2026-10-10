# El meu diari d’avui

Aplicació web gratuïta per a iPhone, publicada amb GitHub Pages.

## Estructura

- `index.html`: estructura de la pàgina.
- `assets/scss/styles.scss`: estils font en SCSS.
- `assets/css/styles.css`: CSS ja compilat que utilitza el navegador.
- `assets/js/app.js`: interaccions i interfície.
- `assets/js/storage.js`: emmagatzematge local de PDF amb IndexedDB.
- `assets/js/sw.js`: lògica de memòria cau.
- `sw.js`: fitxer pont mínim necessari a l’arrel perquè el service worker controli tota l’aplicació a GitHub Pages.
- `assets/img/`: icones de l’aplicació.
- `manifest.webmanifest`: configuració per instal·lar l’aplicació.

## Publicació

Puja **tot el contingut d'aquesta carpeta** a l'arrel del repositori de GitHub Pages, mantenint les subcarpetes.

GitHub Pages no compila SCSS. Si canvies `assets/scss/styles.scss`, cal regenerar `assets/css/styles.css` amb Sass:

```bash
npx sass assets/scss/styles.scss assets/css/styles.css --style=expanded
```

Per provar-la localment, utilitza un servidor HTTP local (els mòduls JS no funcionen correctament obrint `index.html` amb `file://`).

## Limitacions

El botó de generar obre ChatGPT amb una petició preparada; no crea el PDF automàticament.
Els PDF es guarden localment al navegador amb IndexedDB, no se sincronitzen i es poden perdre si s'esborren les dades del lloc.
