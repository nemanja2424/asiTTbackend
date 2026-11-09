# Napredak backend implementacije

Ažurirano: 5. novembar 2026. Vlasnik evidencije: Technical Lead.

## Trenutno stanje

Faze 1–6 završene. Implementirano svih 35 endpoint-a: auth (4), users (7), departments (8), projects/dodele (10), logs (4), reports (1), dashboard (1). Kod i dokumentacija pregledani su čitanjem, bez izvršavanja. Testiranje i QA vrši isključivo vlasnik; agenti ih ne izvršavaju. Nema preostalih implementacionih faza u odobrenom obimu.

## Usvojene odluke

- Dopuna 6. novembra 2026: direktni manager odeljenja može biti aktivan admin ili manager bez promene sistemske uloge. Admin i dalje može dodeliti workera uz unapređenje; manager koji vrši dodelu zadržava postojeće ograničenje svih članstava kandidata na svoju nadležnost. Prelazak dodeljenog admina ili managera u worker uklanja njegove direktne dodele, a prelazak između admin i manager uloga ih zadržava. Izmene nisu funkcionalno testirane.

- JWT access 30 dana, bez refresh tokena. Logout samo potvrđuje klijentsko uklanjanje tokena; nema serverskog opoziva. Stari token može ponovo važiti nakon aktivacije.
- Kreiranje korisnika vraća privremenu lozinku jednom. Oznaka u password_hash zahteva prvu promenu; ograničeni token ima pristup samo me/logout/change-password. Nakon početne promene nova prijava.
- Manager upravlja samo workerima sa svim članstvima u njegovoj nadležnosti; nova članstva ostaju u njoj.
- Deaktivacija čuva članstva/logove, uklanja direktne projektne dodele i direktna managerska zaduženja; aktivacija ne vraća obrisane dodele.
- Manager vidi projekte koji uključuju njegovu granu, upravlja zajedničkim projektom ali čuva tuđe dodele. Praznim projektom upravlja samo admin.
- Samo admin promoviše worker nalog u manager pri dodeli odeljenju.
- Slojevi routes/services/repositories i zajednički moduli su odobreni. Flask, psycopg 3, PyJWT, python-dotenv, Werkzeug.
- Europe/Belgrade; nedelja od ponedeljka; sav spent_time pripada početku loga. Department zbirovi mogu se preklapati; ukupni zbir broji log jednom.
- Server generiše UUID loga. PATCH projekta dozvoljava start_date. Finished dobija današnji end_date; neusaglašeni datumi se odbijaju.
- Sve osim login zahteva prijavu. Deaktivirane korisnike vidi admin. Manager proširene detalje dobija samo za podređene; worker stablo samo njegova odeljenja.
- JSON snake_case; jedinstvene greške; cursor liste 50/max100; reports podrazumevano tekuća nedelja, dashboard rang-liste tekući mesec.

## Faze i vlasništvo

0. Lead: inspekcija i odluke — završeno; kreirana ova evidencija.
1. Backend Dev: osnova, konfiguracija, DB, greške, paginacija, auth — završeno i pregledano bez izvršavanja.
2. Backend Dev: users/departments — završeno i pregledano bez izvršavanja.
3. Backend Dev: projects/assignments — završeno i pregledano bez izvršavanja.
4. Backend Dev: logs — završeno i pregledano bez izvršavanja.
5. Backend Dev: reports/dashboard — završeno i pregledano bez izvršavanja.
6. Lead: završna inspekcija koda/dokumentacije završena; Helper: konačno usklađivanje dokumentacije — završeno.

Helper poseduje docs/API_MANUAL_TESTING.md i docs/UI_PLAN.md. Backend Dev poseduje aplikacione module i manifest; Lead poseduje ovu evidenciju i lokalnu konfiguraciju. Nema istovremenog vlasništva nad fajlovima.

## Izmenjeni fajlovi

- Faza 1: app.py, __init__.py, config.py, db.py, errors.py, validation.py, pagination.py, auth.py, authorization.py; routes/auth.py, services/auth.py, repositories/auth.py i njihovi __init__.py; requirements.txt, .env.example.
- Lead: BACKEND_PROGRESS.md i ignorisani .env (generisani lokalni signing secrets; DATABASE_URL prazan).
- Helper: docs/API_MANUAL_TESTING.md i docs/UI_PLAN.md — konačno usklađeni sa svih 35 endpoint-a; UI ostaje predlog.
- Faza 2: routes/users.py, routes/departments.py, services/users.py, services/departments.py, services/scope.py, repositories/users.py, repositories/departments.py, repositories/scope.py; app.py i validation.py dopunjeni.
- Faza 3: routes/projects.py, services/projects.py, repositories/projects.py; app.py i validation.py dopunjeni.
- Faza 4: routes/logs.py, services/logs.py, repositories/logs.py; repositories/scope.py, services/scope.py i app.py dopunjeni.
- Faza 5: routes/reports.py, services/reports.py, repositories/reports.py, routes/dashboard.py, services/dashboard.py, repositories/dashboard.py; app.py dopunjen.
- Lead završna dokumentacija: koreni AGENTS.md i backend/AGENTS.md dopunjeni novim stanjem i odlukama; prethodna inspekcija zadržana kao istorijska.

## Otvoreno i sledeći korak

- Podaci za DB konekciju nisu dostavljeni; DATABASE_URL ostaje prazan. Factory izričito odbija praznu konfiguraciju; ne povezuje se na DB pri kreiranju. Ne izmišljati kredencijale, ne izvršavati SQL nad korisničkom bazom.
- Sledeći korak je vlasnikov: uneti DATABASE_URL, obezbediti već postavljenu šemu i aktivnog admina, instalirati requirements i pokrenuti API prema docs/API_MANUAL_TESTING.md; vlasnik zatim vodi ručno testiranje. Agenti ništa od toga nisu izvršavali.
- Završni pregled: 35 deklaracija ruta i 7 registrovanih Blueprints; SQL pozivi nisu u routes/services; nema TODO/FIXME stubova u aplikacionim modulima. Git inventar pokazuje izmene samo backend implementacije/dokumentacije i korenog AGENTS konteksta; SQL/UI/dijagram/generator nisu menjani. .env je potvrđeno ignorisan. Primeri u dokumentaciji su ilustrativni, nisu snimljeni odgovori.
- Nema nerešenih produktnih odluka koje blokiraju dovršeni backend obim. Ostaju operativni preduslovi DB/admin, dokumentovano ograničenje inactive foreign dodela, stateless logout bez opoziva i zasebne buduće desktop odluke (idle/offline/oporavak/token storage). Nije implementiran refresh, reset lozinke, seed ili klijentska idempotentnost.
- Inspekcija faze 5: SQL filtered_logs ostavlja jedan red po logu; total/count odvojeni od grupisanja; integer konverzija SUM; date_trunc u app zoni, nedelje od ponedeljka. Manager department filter i output su intersect scope; worker samo svoji logovi. Type određuje default group_by. Dashboard fixed cards nezavisne od perioda, period rang-lista default ceo tekući mesec; top10, recent_logs5 alltime. Aktivni projekti active i nearhivirani. Admin active_projects je broj, ostale uloge lista; manager ima i active_project_count. Ovo nije funkcionalna verifikacija.
- Inspekcija faze 4: server UUID, owner iz autentifikacije; active/not archived/effective provere zajedno sa INSERT; trajanje celobrojno, BIGINT, SQL exclusion 409; hidden detail 404; DELETE admin fizički sa 200 message. GET podrazumeva tekuću Belgrade nedelju, samo jedan datum ostavlja drugu granicu otvorenom, date_to uključiv, pripadnost preko start_time. Department filter koristi direktno trenutno članstvo. Ovo nije funkcionalna verifikacija.
- Inspekcija faze 3: efektivni učesnici UNION, assignment_sources direct/department, ukupan SUM kao int; datumi/status menjaju se transakciono. Cursor za projects i participants; detalji projekta sadrže sve učesnike. Manager self-participant nije poseban izuzetak za vidljivost projekta. Shared full-list PUT čuva tuđe dodele. Poznato ograničenje: postojeća tuđa neaktivna dodela blokira manager PUT zbog zahteva očuvanja i zabrane podnošenja neaktivnih entiteta; admin mora prvo ukloniti takvu dodelu.
- Read nadležnost logs/reports/dashboard obuhvata bilo koje članstvo u manager grani, sve uloge i istorijske logove neaktivnih članova. To je odvojeno od strožeg pravila upravljanja worker nalozima.
- Inspekcija faze 2: SQL je izdvojen u repositories; fully_subordinate zahteva worker i neprazna članstva sva u nadležnosti; deaktivacija čisti direktne dodele i manager_id u istoj transakciji. Admin promena manager uloge uklanja zaduženja. Users detail proširena statistika ima total/count i by_project. Flat departments ima cursor, tree kompletnu vidljivu hijerarhiju. Brojači su aktivni direktni članovi/pododeljenja; deaktivirani članovi skriveni neadminima. Prazna članstva posle kreiranja dozvoljena. Ovo nije funkcionalna verifikacija.
- Inspekcija faze 1: usklađen envelope items/next_cursor i details uvek objekat; DB koristi SERIALIZABLE i retry cele callback transakcije do 3 pokušaja; tzdata uključen za Windows. JWT HS256 sa obaveznim claims, provera aktivnosti/uloge iz DB, temporary$ hash marker. Ograničeni token posle početne promene više ne važi. Ovo nije funkcionalna verifikacija.
- Pri nastavku prvo uporediti ovu evidenciju sa stvarnim kodom i git diff-om.

SQL šema, generator/dijagram i UI se ne menjaju. Nijedan test ili ručni QA nije izvršen.
