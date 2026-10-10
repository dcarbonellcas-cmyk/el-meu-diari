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

El botó obre directament `diaris/avui.pdf`, després de comprovar que l’edició és de la data actual a Europe/Madrid. No obre ChatGPT ni presenta una edició antiga com si fos d’avui.

## Diari automàtic

`.github/workflows/diari.yml` genera el document cada hora (minut 17 UTC), en cada canvi a main i manualment des d’Actions. GitHub pot endarrerir les execucions programades; les programacions poden desactivar-se després de 60 dies sense activitat al repositori.

El generador `scripts/generate_diary.py` consulta els RSS públics de 3CatInfo i VilaWeb. Inclou fins a 20 notícies publicades aquell dia, alternant fonts i mantenint l’ordre editorial de cada canal. Són titulars i fragments breus, amb enllaços als articles originals; no és una redacció amb IA ni una verificació independent de les afirmacions dels mitjans. Les fotografies disponibles provenen del RSS de 3CatInfo i s’atribueixen a la font.

No requereix claus d’IA. La font de GitHub Pages ha de ser **GitHub Actions**. El procés genera el PDF i `latest.json` dins de l’artefacte publicat; no afegeix commits automàtics a main. Si falla una font, el document ho indica. Si fallen totes, el desplegament falla i conserva el lloc anterior; l’aplicació avisa si l’edició és antiga.

Per provar el generador: `python scripts/generate_diary.py --output diaris` (requereix reportlab).
Els PDF es guarden localment al navegador amb IndexedDB, no se sincronitzen i es poden perdre si s'esborren les dades del lloc.
