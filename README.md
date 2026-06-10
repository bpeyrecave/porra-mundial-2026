# Porra Mundial 2026 🏆

Dashboard de predicciones para el Mundial USA·MEX·CAN 2026.  
Participantes: Marc · Eugènia · Berta · José Luis

**Demo:** abre `index.html` directamente en el navegador, o visita la URL de GitHub Pages una vez configurado.

---

## Setup inicial (una sola vez)

### 1. Crear el repositorio en GitHub

```bash
# En tu ordenador, desde la carpeta porra-mundial-2026/
git init
git add .
git commit -m "feat: initial dashboard setup"

# En GitHub: New repository → nombre "porra-mundial-2026" → Private → Create
# Luego:
git remote add origin https://github.com/bpeyrecave/porra-mundial-2026.git
git branch -M main
git push -u origin main
```

### 2. Activar GitHub Pages

- En el repo → **Settings → Pages**
- Source: **Deploy from a branch** → Branch: `main` / `/ (root)`
- Guardar. En ~1 minuto el dashboard estará en:  
  `https://bpeyrecave.github.io/porra-mundial-2026/`

### 3. API Key para resultados en vivo

1. Regístrate gratis en [football-data.org](https://www.football-data.org/) (plan gratuito, no hace falta tarjeta)
2. Copia tu API key
3. En GitHub → **Settings → Secrets and variables → Actions → New repository secret**
   - Name: `FOOTBALL_DATA_API_KEY`
   - Value: tu API key

El workflow en `.github/workflows/update-results.yml` se ejecutará cada hora automáticamente y actualizará los resultados.  
También puedes lanzarlo manualmente desde **Actions → Update WC 2026 Results → Run workflow**.

---

## Añadir picks de otro participante

Cuando Marc, Eugènia o José Luis te pasen su Excel rellenado:

```bash
# Desde la carpeta porra-mundial-2026/
python scripts/extract_picks.py "ruta/al/archivo.xlsx" Marc
python scripts/extract_picks.py "ruta/al/archivo.xlsx" Eugenia
python scripts/extract_picks.py "ruta/al/archivo.xlsx" "Jose Luis"

git add data/picks/
git commit -m "feat: add Marc/Eugenia/Jose Luis picks"
git push
```

El dashboard se actualiza automáticamente al hacer push.

> **Nota:** el script `extract_picks.py` espera el mismo formato de Excel que "Porra - Mundial 2026 - EXCEL FINAL". Requiere: `pip install openpyxl`

---

## Sistema de puntuación

| Fase | Puntos |
|------|--------|
| Fase de grupos — resultado correcto (1X2) | 1 pt |
| Fase de grupos — marcador exacto | 3 pts |
| Dieciseisavos — ganador correcto | 5 pts |
| Octavos — ganador correcto | 10 pts |
| Cuartos — ganador correcto | 15 pts |
| Semifinales — ganador correcto | 25 pts |
| Tercer puesto — ganador correcto | 15 pts |
| Final — ganador correcto | 50 pts |
| Bota de Oro | 10 pts |

---

## Estructura del repo

```
porra-mundial-2026/
├── .github/workflows/update-results.yml   # Auto-fetch resultados cada hora
├── data/
│   ├── picks/
│   │   ├── berta.json       # Picks de Berta ✅
│   │   ├── marc.json        # Pendiente
│   │   ├── eugenia.json     # Pendiente
│   │   └── jose_luis.json   # Pendiente
│   ├── results.json         # Resultados reales (auto-actualizado)
│   └── team_names.json      # Mapeo español ↔ inglés para la API
├── scripts/
│   ├── extract_picks.py     # Extrae picks de un Excel
│   └── fetch_results.py     # Descarga resultados de football-data.org
└── index.html               # El dashboard
```
