# Pulse AI V1 — dozvoljeni izvor živih podataka

## Alat `reports`

`GET /api/reports`

Koristi se **samo kada je za odgovor potreban stvarni izveštaj o radu**: broj sati, poređenje projekata/korisnika/odeljenja, vremenski trend, procentualni udeo ili druga agregacija koju postojeća ruta zaista vraća.

### Dozvoljeni parametri (prema usvojenoj specifikaciji)

| Parametar | Vrednosti / značenje |
| --- | --- |
| `type` | `time`, `projects`, `users`, `departments` |
| `date_from` | početni datum; format proveriti prema stvarnom API ugovoru |
| `date_to` | završni datum; format proveriti prema stvarnom API ugovoru |
| `group_by` | `day`, `week`, `month`, `project`, `user`, `department` |
| `project_id` | ID projekta |
| `user_id` | ID korisnika |
| `department_id` | ID odeljenja |
| `project_status` | status projekta, prema važećem API ugovoru |
| `user_role` | uloga korisnika, prema važećem API ugovoru |
| `include_subdepartments` | boolean |

Svi navedeni tipovi mogu se kombinovati sa svim navedenim grupisanjima. Bez oba datuma Reports podrazumeva tekuću nedelju; jedan izostavljen datum predstavlja otvorenu granicu. Odgovor sadrži `type`, `group_by`, `date_from`, `date_to`, ukupne `spent_time` (aktivne sekunde) i `log_count`, te `items` sa `key`, `label`, `spent_time` i `log_count`.

### Autorizacija

- `admin`: firmom obuhvaćeni podaci.
- `manager`: izveštaji nad zaposlenima i pododeljenjima pod njegovom nadležnošću; uključujući njihov rad na projektima izvan direktnih dodela odeljenju.
- `worker`: samo sopstveni podaci; svi tipovi izveštaja u okviru tog ograničenja.
- Autorizacija se primenjuje na svaki filter; `include_subdepartments` ne može proširiti pravo izvan stvarne nadležnosti.

Backend je jedini autoritet za pristup podacima; router samo predlaže parametre. Nije dozvoljeno zaobilaženje ovlašćenja niti pozivanje proizvoljnih ruta.

### Izbor identifikatora

Ne izmišljati UUID-jeve. Ako korisnik navede naziv projekta ili odeljenja, a odgovarajući ID nije dostavljen u ograničenom katalogu autorizovanih entiteta, vratiti `needs_clarification` ili zahtev za bezbedno razrešenje naziva; ne pogađati ID.

U ovoj verziji katalog nije dostupan. Za trenutnog korisnika koristi `user_id: "self"`; backend ga zamenjuje identifikatorom prijavljenog korisnika. Ostale identifikatore ne predlaži.

### Primer kada alat NIJE potreban

- „Šta je Work Pulse?“ — statički kontekst kompanije.
- „Kako funkcioniše pie chart?“ — opšte objašnjenje.
- „Napiši mi Markdown listu koraka za organizaciju projekta.“ — generalna pomoć.
- „Koje podatke ovaj AI može da analizira?“ — opis mogućnosti.

### Primer kada JESTE potreban

- „Koliko smo radili prošlog meseca?“
- „Prikaži pie chart sati po projektima.“
- „Uporedi dane u tekućoj nedelji.“
- „Koje odeljenje ima najviše priznatog aktivnog vremena?“
