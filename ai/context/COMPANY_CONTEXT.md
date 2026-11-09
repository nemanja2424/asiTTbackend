# Work Pulse / ASI Solutions — statički kontekst kompanije

> Status: početna, konzervativna verzija. Ovaj dokument sadrži samo poznate činjenice; vlasnik treba da dopuni specifične podatke o kompaniji pre produkcionog korišćenja.

## Identitet

- **ASI Solutions** je organizacija koja razvija i koristi aplikaciju **Work Pulse**.
- **Work Pulse** je Windows desktop aplikacija za organizaciju rada, upravljanje projektima i odeljenjima, evidenciju aktivnog radnog vremena, izveštaje i zajedničke biblioteke fajlova.
- **Pulse AI** je AI asistent integrisan u Work Pulse. U prvoj verziji daje informativne odgovore i, gde su podaci dostupni i ovlašćenja dozvoljavaju, analizira postojeće izveštaje. Ne menja podatke.

## Organizacija unutar Work Pulse-a

- Postoji jedna kompanija, sa hijerarhijom odeljenja i pododeljenja.
- Uloge korisnika su `admin`, `manager` i `worker`.
- Korisnik može biti član više odeljenja. Nadležnost managera može se prostirati na pododeljenja.
- Projekti mogu imati direktno dodeljene korisnike i dodeljena odeljenja; dodela odeljenja obuhvata i njegove pododeljenja.
- Aktivno radno vreme meri se desktop štopericom; pri slanju završenog zapisa aktivno vreme može biti manje od ukupnog trajanja intervala (zbog AFK perioda).

## Šta OVAJ dokument ne sadrži

Ovaj statički kontekst nije izvor ažurnih, pojedinačnih podataka: imena zaposlenih, članstva, statusi projekata, trenutne managerske dodele, sati rada, statistika, fajlovi i druga promenljiva stanja. Za te činjenice mora se koristiti relevantan autorizovan izvor; trenutno je za Pulse AI V1 odobren samo izveštajni API.

## Granice u prvoj verziji

- Nema agentskih radnji: bez kreiranja, izmene, brisanja, zakazivanja ili upravljanja nalozima i projektima.
- Nema RAG-a, indeksiranja ili čitanja fajlova biblioteke.
- Pulse AI ne izmišlja interne činjenice koje nisu u ovom dokumentu ili dobijenom API odgovoru.
- Podaci vidljivi pojedinom korisniku zavise od već postojećih backend pravila pristupa.

## Podaci o firmi koje vlasnik tek treba da potvrdi

- Misija i delatnosti ASI Solutions, zvanični opis, link sajta.
- Interni procesi, očekivanja od zaposlenih, kontakt za podršku.
- Pravila o privatnosti, čuvanju razgovora i dozvoljenoj upotrebi AI servisa.

Ne dopunjavati ove stavke pretpostavkama.
