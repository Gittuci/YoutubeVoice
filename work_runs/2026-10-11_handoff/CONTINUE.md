# Folytatás másik gépen

A GitHub-mentés a kódot és az átadási dokumentációt tartalmazza. Az eredeti `output/video.mp4` már korábbról verziókövetett. A felhasználó kérésére a `media_and_metadata.zip` NEM kerül GitHubra: ezt külön kell átmásolni erről a gépről a másikra. A ZIP 35 fájlt tartalmaz, eredeti projektbeli relatív útvonallal: a hat kiválasztott tiszta WAV/SRT párt, a feltöltési jegyzéket, a hatnyelvű címeket/leírásokat és a kapcsolódó ellenőrzési bizonyítékokat. A `manifest.json` a ZIP és minden tartalmazott fájl SHA-256 értékét rögzíti; a csomag elkészítésekor mindet ellenőriztük.

1. A másik gépen frissítsd a megfelelő projektet: `git pull --ff-only`. Ha helyi módosítások miatt ez nem lehetséges, őrizd meg őket; ne használj reset/clean parancsot.
2. Másold át külön a ZIP-et a másik gép `work_runs/2026-10-11_handoff/` mappájába. A projekt gyökeréből PowerShellben bontsd ki a csomagot:

   ```powershell
   Expand-Archive -LiteralPath .\work_runs\2026-10-11_handoff\media_and_metadata.zip -DestinationPath .
   ```

   Nem használunk `-Force` kapcsolót: meglévő helyi fájlokat ne írjunk felül ellenőrzés nélkül. A ZIP-ben minden útvonal a projekt gyökeréhez viszonyított.
3. Az új chat olvassa el az `AGENTS.md` szerinti négy dokumentumot, különösen a `docs/CODEX_HANDOFF.md` legutolsó átadását. Az első nyitott kérdés az angol alap szöveg és hang a nem támogatott nyelvű nézőknek; ez még nincs átállítva.

A `.venv`, `.env`, `vertex-key.json` és `.local/youtube/` nincs a csomagban. A másik gépen a saját projektkörnyezetet és hitelesítést kell használni; a böngésző bejelentkezése sem GitHub-adat. A teljes korábbi `output/test_runs/`, az alternatív hangpróbák és a nyers szolgáltatói eredmények nem részei ennek a válogatott csomagnak, az eredeti gépen megmaradnak. Az itt mentett hat végleges narrációból nem kell újat generálni.
