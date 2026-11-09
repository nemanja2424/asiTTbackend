# Backend Dev — ASI Time Tracker

Ova pravila važe za `backend/` i dopunjuju [koreni AGENTS.md](../AGENTS.md), koji je glavni izvor poslovnih pravila i dogovorenih odluka. Komunikacija i izveštaji su na srpskom. Pre izmene pročitati relevantni postojeći kod i dokumentaciju.

## Uloga i granice

- Jedan Codex agent samostalno obrađuje Python/Flask backend, REST API, autorizaciju, poslovnu logiku i PostgreSQL upite, bez subagenata i delegiranja.
- Raditi u okviru konkretnog zadatka i ne proširivati njegov obim bez potrebe.
- Agent usklađuje API ugovor, arhitekturu i integraciju; nedostajuće produktne odluke razjašnjava sa vlasnikom.
- Ne menjati samostalno poslovna pravila, stek ili uvoditi nove velike zavisnosti. DB biblioteka, autentifikacioni tokovi i detaljni API ugovor nisu unapred izabrani ovim dokumentom.
- Ne delegirati. UI i backend menjati zajedno kada to zahteva konkretan zadatak, uz očuvanje granica komponenti.

## Organizacija implementacije

- Rute obrađuju HTTP zahteve, ulaznu validaciju i odgovore prema dogovorenom API ugovoru.
- Poslovni servisi centralizuju autorizaciju, poslovna pravila i granice transakcija. Ne oslanjati se na UI kao izvor ovlašćenja.
- Sloj pristupa bazi koristi parametrizovane upite i izdvaja SQL, uključujući rekurzivne upite i agregacije, od HTTP obrade.
- Baza čuva integritet podataka; backend sprovodi dogovorena pravila pristupa i poslovne operacije. Desktop pristupa podacima preko API-ja, bez direktnog pristupa bazi.
- Greške obrađivati eksplicitno i dosledno. Povezane poslovne izmene obavljati u istoj transakciji; ponašanje pri konkurentnim izmenama uskladiti sa pravilima iz korenog dokumenta.
- Tajne i konfiguraciju okruženja čitati iz promenljivih okruženja. Ne unositi lozinke, tokene ili druge tajne u kod, odgovore, logove ili dokumentaciju.

## Baza i postojeći artefakti

- Važeća implementacija baze je [db/schema.sql](../db/schema.sql). Pre SQL izmena pročitati šemu i poslovna pravila u korenom dokumentu.
- Šemu menjati isključivo kroz posebno odobren zadatak, nakon procene uticaja. Skripta je namenjena novoj bazi i nije migracija niti skripta za ponovljeno izvršavanje.
- Ne izvršavati SQL nad korisničkim bazama bez odgovarajuće instrukcije. Ne zaobilaziti postojeća ograničenja radi prilagođavanja aplikacionog koda.
- Dijagram i generator ne menjati niti pokretati u okviru zadataka koji to ne traže.

## Način rada i izveštavanje

- Pre početka utvrditi cilj, dozvoljene fajlove, očekivano ponašanje, zavisnosti, zabrane i kriterijume prihvatanja iz zadatka. Ne proširivati obim samostalno.
- Blokade i pitanja koja utiču na ponašanje proizvoda razjasniti sa vlasnikom.
- Testiranje vodi vlasnik projekta. Ne pisati niti pokretati testove, ne sprovoditi ručni QA i ne postavljati infrastrukturu za testiranje. Dozvoljena je osnovna inspekcija koda radi uočavanja očiglednih grešaka.
- Završni izveštaj navodi šta je implementirano, izmenjene fajlove, nalaze inspekcije i nerešena pitanja ili pretpostavke. Navesti da testovi nisu izvršavani prema projektnoj politici; ne predstavljati inspekciju kao potvrdu funkcionalne ispravnosti.

Pri uspostavljanju ovih pravila 4. novembra 2026. `app.py` je prazan; backend funkcionalnosti opisane ovde predstavljaju odgovornosti buduće implementacije, ne postojeće mogućnosti aplikacije.

## Implementacija — 5. novembar 2026.

Prethodni pasus je istorijsko stanje. Sada postoji implementacija 35 endpoint-a kroz Flask Blueprints, services i repositories. Zavisnosti su u requirements.txt, lokalna konfiguracija u ignorisanom .env, a primer bez tajni u .env.example. Koriste se psycopg 3 parametrizovani upiti, SERIALIZABLE transakcije sa ograničenim ponavljanjem, PyJWT access token od 30 dana i Werkzeug scrypt hash.

Naknadno usvojene odluke i fazna evidencija su u BACKEND_PROGRESS.md. Refresh nije deo implementacije; logout je klijentski bez opoziva JWT-a. Novi nalozi dobijaju privremenu lozinku sa obaveznom promenom. Serverski UUID loga znači da API nema klijentsku idempotentnost. SQL šema i UI nisu menjani. DB konekcioni podaci nisu dostavljeni, DATABASE_URL je prazan; prvi aktivan admin i postavljena šema su preduslovi.

Dokumentacija ručnog testiranja: docs/API_MANUAL_TESTING.md. Predlog UI-ja: docs/UI_PLAN.md. Implementacija je pregledana čitanjem koda, bez izvršavanja aplikacije, testova, QA ili SQL-a. Ne predstavljati je kao funkcionalno verifikovanu. Pri nastavku prvo pročitati BACKEND_PROGRESS.md i uporediti sa stvarnim fajlovima.

Profilne fotografije: `routes/profile_image.py`, `services/profile_image.py` i `repositories/profile_image.py`; slike se čuvaju izvan baze, a obrada koristi Pillow. `db/migrations/001_add_profile_img.sql` je pripremljena za vlasnikovo ručno izvršavanje; nije izvršena ni testirana. Važeći API ugovor je u `../docs/API_MANUAL_TESTING.md`.

Biblioteke fajlova koriste `routes/resources.py`, `services/resources.py` i `repositories/resources.py`. Migracija `../db/migrations/002_resource_library.sql` nije izvršena; privatno skladište, limiti, API i poznata ograničenja opisani su u `../docs/API_MANUAL_TESTING.md` i `../docs/RESOURCE_DEPLOYMENT.md`. Testovi i QA nisu izvršeni.
