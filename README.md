# van-mufwar-videos

Vidéos TikTok « Astuce Excel du jour » de @bleuddymufwar (Ingénieur Van MUFWAR), publiées via Metricool.

- `videos/` : vidéos MP4 (lien public utilisé par Metricool)
- `specs/` : contenu de chaque vidéo
- `outils/render.py` : générateur de vidéo
- `historique.md` : astuces déjà publiées

## Règles de publication
- Écran de fin : `render.py` affiche automatiquement « Quelle formule veux-tu demain ? Écris-la en commentaire ! » (champ facultatif `comment_cta` dans la spec).
- Légende TikTok : toujours inclure « Quelle formule veux-tu demain ? Écris-nous en commentaire 👇 » avant les hashtags.

## Variété (depuis le 04/11/2026)
- Chaque spec a un champ `"theme"` : classique, neon, epure, vert_excel, bleu_nuit, soleil, violet, degrade, papier, terre (palette, fond, disposition, police, animations, style du résultat, écran de fin, musique).
- Champs facultatifs pour forcer : `"music"` (lofi, lofi_nuit, rumba, electro, piano, marimba, likembe, percussions), `"layout"` (classic, banner, card, laptop), `"cta_style"` (pulse, card, bar).
- `"mode": "steps"` pour les astuces sans formule (raccourcis, menus, mise en forme) : `steps`, `select`, `fills`, `paints` — voir l'en-tête de `outils/render.py`.
- Sans `"theme"`, les anciennes specs gardent le look d'origine.
