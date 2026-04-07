"""
Mini-TFL: Static legal intelligence system for Prima Facie.
Replicates key TFL API features using only internally extracted features.
No client data is sent externally — all references are inferred from
classified field, AML indicators, key facts, deadlines, and raw email text.

Replicated TFL features:
1. Citation extraction (POST /references/extract) — regex on raw email
2. Article content (GET /legislation/{id}/articles/{number}) — stored summaries
3. Court decisions (GET /court-decisions) — landmark rulings per field + keywords
4. Cross-references (GET /legislation/{id}/references) — inter-law links
5. Keyword-to-article mapping — key_facts → specific articles
"""

import re

# =============================================================================
# 1. ARTICLE CONTENT DATABASE — actual article text/summaries
#    Replaces: TFL GET /legislation/{id}/articles/{number}
# =============================================================================

ARTICLE_CONTENT = {
    # --- GDPR ---
    "GDPR:33": {
        "law": "GDPR",
        "number": "33",
        "title": "Priglasitev kršitve varstva osebnih podatkov nadzornemu organu",
        "content": "Upravljavec brez nepotrebnega odlašanja in, kadar je izvedljivo, najpozneje v 72 urah po seznanitvi s kršitvijo varstva osebnih podatkov, o njej uradno obvesti nadzorni organ. Uradno obvestilo vsebuje: opis narave kršitve, kategorije in približno število posameznikov, kontaktno točko, opis verjetnih posledic, opis ukrepov.",
        "deadline": "72 ur od odkritja kršitve",
    },
    "GDPR:34": {
        "law": "GDPR",
        "number": "34",
        "title": "Sporočanje kršitve varstva osebnih podatkov posamezniku",
        "content": "Kadar je verjetno, da kršitev varstva osebnih podatkov povzroči veliko tveganje za pravice in svoboščine posameznikov, upravljavec brez nepotrebnega odlašanja o kršitvi obvesti posameznika, na katerega se nanašajo osebni podatki.",
    },
    "GDPR:82": {
        "law": "GDPR",
        "number": "82",
        "title": "Pravica do odškodnine in odgovornost",
        "content": "Vsaka oseba, ki je utrpela premoženjsko ali nepremoženjsko škodo zaradi kršitve te uredbe, ima pravico od upravljavca ali obdelovalca prejeti odškodnino za nastalo škodo.",
    },
    "GDPR:83": {
        "law": "GDPR",
        "number": "83",
        "title": "Splošni pogoji za naložitev upravnih glob",
        "content": "Kršitve temeljnih načel obdelave in pravic posameznikov: globe do 20.000.000 EUR ali do 4 % celotnega svetovnega letnega prometa. Kršitve obveznosti upravljavca/obdelovalca: globe do 10.000.000 EUR ali do 2 % prometa.",
        "note": "Višina globe je odvisna od narave, teže, trajanja kršitve in ukrepov za zmanjšanje škode.",
    },
    # --- ZVOP-2 ---
    "ZVOP-2:40": {
        "law": "ZVOP-2",
        "number": "40",
        "title": "Priglasitev kršitve Informacijskemu pooblaščencu",
        "content": "Upravljavec priglasi kršitev varstva osebnih podatkov Informacijskemu pooblaščencu RS najpozneje v 72 urah po seznanitvi s kršitvijo. Priglasitev vsebuje opis kršitve, kontaktne podatke pooblaščene osebe, opis verjetnih posledic in opis sprejetih ukrepov.",
    },
    "ZVOP-2:41": {
        "law": "ZVOP-2",
        "number": "41",
        "title": "Obveščanje posameznikov o kršitvi",
        "content": "Kadar kršitev varstva osebnih podatkov lahko povzroči veliko tveganje za pravice posameznikov, upravljavec brez nepotrebnega odlašanja obvesti prizadete posameznike v jasnem in preprostem jeziku.",
    },
    "ZVOP-2:102": {
        "law": "ZVOP-2",
        "number": "102",
        "title": "Globe za kršitve",
        "content": "Globe za kršitve določb tega zakona so od 4.170 EUR do 20.000.000 EUR za pravne osebe, odvisno od teže kršitve.",
    },
    # --- ZDR-1 ---
    "ZDR-1:83": {
        "law": "ZDR-1",
        "number": "83",
        "title": "Razlogi za redno odpoved pogodbe o zaposlitvi",
        "content": "Delodajalec lahko redno odpove pogodbo o zaposlitvi iz naslednjih razlogov: poslovni razlog (prenehanje potreb po opravljanju dela), razlog nesposobnosti (nedoseganje pričakovanih rezultatov), krivdni razlog (kršitev pogodbene ali druge obveznosti iz delovnega razmerja).",
    },
    "ZDR-1:85": {
        "law": "ZDR-1",
        "number": "85",
        "title": "Odpoved iz poslovnega razloga",
        "content": "Delodajalec lahko odpove pogodbo o zaposlitvi, če prenehajo potrebe po opravljanju določenega dela pod pogoji iz pogodbe o zaposlitvi, zaradi ekonomskih, organizacijskih, tehnoloških, strukturnih ali podobnih razlogov na strani delodajalca.",
    },
    "ZDR-1:87": {
        "law": "ZDR-1",
        "number": "87",
        "title": "Odpoved iz krivdnega razloga",
        "content": "Delodajalec lahko delavcu odpove pogodbo o zaposlitvi, če delavec krši pogodbene ali druge obveznosti iz delovnega razmerja. Pred redno odpovedjo iz krivdnega razloga mora delodajalec delavca pisno opozoriti na izpolnjevanje obveznosti in možnost odpovedi.",
    },
    "ZDR-1:89": {
        "law": "ZDR-1",
        "number": "89",
        "title": "Postopek pred redno odpovedjo iz poslovnega razloga ali razloga nesposobnosti",
        "content": "Delodajalec mora pred redno odpovedjo iz poslovnega razloga ali razloga nesposobnosti preveriti, ali je mogoče delavca zaposliti pod spremenjenimi pogoji ali na drugih delih, ali ga je mogoče dokvalificirati za delo, ki ga opravlja, oziroma prekvalificirati za drugo delo.",
    },
    "ZDR-1:108": {
        "law": "ZDR-1",
        "number": "108",
        "title": "Odpravnina ob odpovedi iz poslovnih razlogov ali razloga nesposobnosti",
        "content": "Delavec, ki mu je odpovedana pogodba iz poslovnih razlogov ali razloga nesposobnosti, je upravičen do odpravnine: 1/5 osnove za vsako leto dela pri delodajalcu (do 5 let), 1/4 osnove (5–15 let), 1/3 osnove (nad 15 let). Osnova je povprečna mesečna plača delavca v zadnjih 3 mesecih.",
    },
    "ZDR-1:200": {
        "law": "ZDR-1",
        "number": "200",
        "title": "Sodno varstvo",
        "content": "Delavec, ki meni, da delodajalec ne izpolnjuje obveznosti iz delovnega razmerja ali krši katero od njegovih pravic, lahko v roku 30 dni od roka za izpolnitev obveznosti oziroma od dneva, ko je izvedel za kršitev pravice, zahteva sodno varstvo pred pristojnim delovnim sodiščem.",
        "deadline": "30 dni od kršitve",
    },
    # --- ZZPri ---
    "ZZPri:7": {
        "law": "ZZPri",
        "number": "7",
        "title": "Prepoved povračilnih ukrepov",
        "content": "Prepovedani so vsi povračilni ukrepi zoper prijavitelja, vključno z odpovedjo delovnega razmerja, degradacijo, premestitivijo, zastraševanjem, šikaniranjem in diskriminacijo.",
    },
    # --- ZGD-1 ---
    "ZGD-1:3": {
        "law": "ZGD-1",
        "number": "3",
        "title": "Vrste gospodarskih družb",
        "content": "Gospodarske družbe so: družba z neomejeno odgovornostjo (d.n.o.), komanditna družba (k.d.), družba z omejeno odgovornostjo (d.o.o.), delniška družba (d.d.), komanditna delniška družba (k.d.d.) in evropska delniška družba (SE).",
    },
    "ZGD-1:473": {
        "law": "ZGD-1",
        "number": "473",
        "title": "Ustanovitev družbe z omejeno odgovornostjo",
        "content": "Družbo z omejeno odgovornostjo (d.o.o.) lahko ustanovi ena ali več fizičnih ali pravnih oseb z družbeno pogodbo. Najnižji osnovni kapital je 7.500 EUR. Najnižji znesek vložka je 50 EUR.",
    },
    "ZGD-1:474": {
        "law": "ZGD-1",
        "number": "474",
        "title": "Družbena pogodba",
        "content": "Družbena pogodba mora vsebovati: ime in sedež družbe, dejavnost, znesek osnovnega kapitala, znesek vsakega osnovnega vložka in seznam družbenikov s podatki o vsakem družbeniku.",
    },
    "ZGD-1:529": {
        "law": "ZGD-1",
        "number": "529",
        "title": "Skrbni pregled (due diligence)",
        "content": "Pri prevzemih in združitvah je prevzemnik upravičen izvesti skrbni pregled ciljne družbe, ki obsega finančni, pravni, davčni in poslovni pregled. Ciljna družba zagotovi dostop do dokumentacije v podatkovni sobi.",
    },
    "ZGD-1:580": {
        "law": "ZGD-1",
        "number": "580",
        "title": "Združitev — splošne določbe",
        "content": "Združitev je mogoča kot pripojitev (ena družba se pripoji k drugi) ali spojitev (dve ali več družb se spojita v novo družbo). Potrebna je priprava pogodbe o združitvi, revizija in soglasje skupščin.",
    },
    "ZGD-1:680": {
        "law": "ZGD-1",
        "number": "680",
        "title": "Podružnice tujih podjetij",
        "content": "Tuja podjetja lahko v RS opravljajo pridobitno dejavnost prek podružnice. Podružnica se vpiše v sodni register. Potrebni dokumenti: akt o ustanovitvi, izpisek iz matičnega registra, podatki o zastopniku.",
    },
    # --- ZPre-1 ---
    "ZPre-1:12": {
        "law": "ZPre-1",
        "number": "12",
        "title": "Obveznost prevzemne ponudbe",
        "content": "Oseba, ki doseže prevzemni prag (1/3 glasovalnih pravic v ciljni družbi), mora v 30 dneh objaviti prevzemno ponudbo za vse preostale delnice ciljne družbe.",
        "deadline": "30 dni od dosega praga",
    },
    # --- ZIL-1 ---
    "ZIL-1:10": {
        "law": "ZIL-1",
        "number": "10",
        "title": "Pogoji za patentiranje izuma",
        "content": "Patent se podeli za izum s kateregakoli področja tehnike, ki je nov, na inventivni ravni in industrijsko uporabljiv.",
    },
    "ZIL-1:18": {
        "law": "ZIL-1",
        "number": "18",
        "title": "Pravica do patenta",
        "content": "Pravica do patenta pripada izumitelju ali njegovemu pravnemu nasledniku. Če je izum nastal v delovnem razmerju, pripada pravica delodajalcu, če ni s pogodbo določeno drugače.",
    },
    # --- ZASP ---
    "ZASP:5": {
        "law": "ZASP",
        "number": "5",
        "title": "Avtorska dela",
        "content": "Avtorska dela so zlasti: govorjena dela, pisana dela, računalniški programi, glasbena dela, gledališka dela, filmska dela, likovna dela, arhitekturna dela, kartografska dela, predstavitve znanstvene ali tehnične narave.",
    },
    "ZASP:80": {
        "law": "ZASP",
        "number": "80",
        "title": "Prenos materialnih avtorskih pravic",
        "content": "Materialne avtorske pravice se lahko prenesejo s pogodbo. Prenos mora biti izrecen — pravice, ki niso izrecno navedene v pogodbi, se štejejo za neprenesene.",
    },
    "ZASP:101": {
        "law": "ZASP",
        "number": "101",
        "title": "Avtorsko delo, ustvarjeno v delovnem razmerju",
        "content": "Če avtor ustvari delo pri izpolnjevanju svojih obveznosti iz delovnega razmerja, se šteje, da so izključne materialne avtorske pravice in druge pravice avtorja na tem delu prenesene na delodajalca za 10 let od dokončanja dela, če ni s pogodbo določeno drugače.",
        "note": "Velja le za dela, ki spadajo v okvir delovnih nalog zaposlenega.",
    },
    # --- ZPPDFT-2 ---
    "ZPPDFT-2:8": {
        "law": "ZPPDFT-2",
        "number": "8",
        "title": "Ocena tveganja s strani zavezanca",
        "content": "Zavezanec izdela in redno posodablja oceno tveganja pranja denarja in financiranja terorizma. Ocena tveganja upošteva: vrsto stranke, geografsko tveganje, tveganje storitev in transakcij, tveganje distribucijskih kanalov.",
    },
    "ZPPDFT-2:16": {
        "law": "ZPPDFT-2",
        "number": "16",
        "title": "Pregled stranke — ukrepi",
        "content": "Ukrepi pregleda stranke vključujejo: ugotavljanje in preverjanje istovetnosti stranke, ugotavljanje dejanskega lastnika, pridobitev podatkov o namenu in predvideni naravi poslovnega razmerja, redno spremljanje poslovnih aktivnosti.",
    },
    "ZPPDFT-2:24": {
        "law": "ZPPDFT-2",
        "number": "24",
        "title": "Ugotavljanje dejanskega lastnika",
        "content": "Zavezanec ugotovi dejanskega lastnika pravne osebe, ki je stranka. Dejanski lastnik je vsaka fizična oseba, ki ima v lasti ali obvladuje stranko, ali fizična oseba, v imenu katere se izvaja transakcija. Prag: 25 % lastniškega deleža ali glasovalnih pravic.",
    },
    "ZPPDFT-2:38": {
        "law": "ZPPDFT-2",
        "number": "38",
        "title": "Poglobljen pregled stranke",
        "content": "Zavezanec izvede poglobljen pregled v primerih višjega tveganja: ko je stranka iz tretje države z visokim tveganjem, pri politično izpostavljenih osebah, pri zapletenih ali neobičajno velikih transakcijah, pri transakcijah brez jasnega ekonomskega ali zakonitega namena.",
    },
    "ZPPDFT-2:40": {
        "law": "ZPPDFT-2",
        "number": "40",
        "title": "Politično izpostavljene osebe",
        "content": "Pri poslovnem razmerju s politično izpostavljeno osebo zavezanec pridobi odobritev višjega vodstva, sprejme ustrezne ukrepe za ugotovitev vira premoženja in vira sredstev ter izvaja poostren stalni nadzor.",
    },
    "ZPPDFT-2:42": {
        "law": "ZPPDFT-2",
        "number": "42",
        "title": "Tretje države z visokim tveganjem",
        "content": "Za stranke iz držav, ki jih Evropska komisija določi kot tretje države z visokim tveganjem, zavezanec izvede poglobljen pregled stranke, pridobi dodatne informacije o stranki in dejanskem lastniku, pridobi odobritev višjega vodstva.",
    },
    "ZPPDFT-2:68": {
        "law": "ZPPDFT-2",
        "number": "68",
        "title": "Poročanje o sumljivih transakcijah",
        "content": "Zavezanec nemudoma poroča Uradu RS za preprečevanje pranja denarja o vsaki transakciji ali stranki, pri kateri obstajajo razlogi za sum pranja denarja ali financiranja terorizma.",
    },
    # --- OZ ---
    "OZ:12": {
        "law": "OZ",
        "number": "12",
        "title": "Svoboda urejanja obligacijskih razmerij",
        "content": "Udeleženci prosto urejajo obligacijska razmerja, ne smejo pa jih urejati v nasprotju z ustavo, prisilnimi predpisi ali moralnimi načeli.",
    },
    "OZ:82": {
        "law": "OZ",
        "number": "82",
        "title": "Razveza pogodbe zaradi neizpolnitve",
        "content": "Če v dvostranskih pogodbah ena stranka ne izpolni svoje obveznosti, lahko druga stranka zahteva izpolnitev ali razveze pogodbo z enostavno izjavo, v obeh primerih pa ima pravico do odškodnine.",
    },
    "OZ:243": {
        "law": "OZ",
        "number": "243",
        "title": "Odškodninska odgovornost",
        "content": "Kdor drugemu povzroči škodo, jo je dolžan povrniti, če ne dokaže, da je škoda nastala brez njegove krivde. Dolžnik je v zamudi, če ne izpolni obveznosti v roku, določenem za izpolnitev.",
    },
    # --- ZPP ---
    "ZPP:11": {
        "law": "ZPP",
        "number": "11",
        "title": "Stvarna pristojnost",
        "content": "Okrajna sodišča so pristojna za spore z vrednostjo spornega predmeta do 20.000 EUR. Okrožna sodišča za spore nad 20.000 EUR in spore iz avtorskih pravic, varstva konkurence, gospodarskih sporov.",
    },
    "ZPP:180": {
        "law": "ZPP",
        "number": "180",
        "title": "Tožba",
        "content": "Tožba mora vsebovati: določen zahtevek (tožbeni predlog), dejstva na katera tožnik opira zahtevek, dokaze s katerimi se ta dejstva ugotavljajo, vrednost spornega predmeta, druge podatke, ki jih mora imeti vsaka vloga.",
    },
    # --- ZJN-3 ---
    "ZJN-3:75": {
        "law": "ZJN-3",
        "number": "75",
        "title": "Razlogi za izključitev",
        "content": "Naročnik iz postopka javnega naročanja izključi ponudnika, če je bil pravnomočno obsojen za kazniva dejanja (korupcija, goljufija, pranje denarja, terorizem), če ne izpolnjuje davčnih obveznosti, ali če je v stečaju.",
    },
    # --- SPZ ---
    "SPZ:37": {
        "law": "SPZ",
        "number": "37",
        "title": "Pridobitev lastninske pravice na nepremičnini",
        "content": "Lastninska pravica na nepremičnini se pridobi z vpisom v zemljiško knjigo na podlagi veljavnega pravnega posla (kupoprodajna pogodba z notarsko overitvijo), odločbe državnega organa ali zakona.",
    },
    # --- GZ-1 ---
    "GZ-1:4": {
        "law": "GZ-1",
        "number": "4",
        "title": "Gradbeno dovoljenje",
        "content": "Gradnja novega objekta, rekonstrukcija ali sprememba namembnosti se lahko izvaja le na podlagi pravnomočnega gradbenega dovoljenja. Vloga se vloži pri pristojnem upravnem organu.",
    },
    # --- ZTuj-2 ---
    "ZTuj-2:33": {
        "law": "ZTuj-2",
        "number": "33",
        "title": "Dovoljenje za prebivanje",
        "content": "Tujec, ki želi v RS prebivati dlje kot 90 dni, mora pridobiti dovoljenje za začasno ali stalno prebivanje. Dovoljenje za začasno prebivanje se izda za čas do enega leta in se lahko podaljšuje.",
    },
    "ZTuj-2:37": {
        "law": "ZTuj-2",
        "number": "37",
        "title": "Enotno dovoljenje za prebivanje in delo",
        "content": "Tujec, ki želi v RS delati in prebivati, pridobi enotno dovoljenje, ki združuje dovoljenje za prebivanje in dovoljenje za delo. Vloga se vloži pri pristojni upravni enoti.",
    },
    # --- ZFPPIPP ---
    "ZFPPIPP:14": {
        "law": "ZFPPIPP",
        "number": "14",
        "title": "Insolventnost",
        "content": "Dolžnik je insolventen, če v daljšem obdobju ni sposoben poravnati vseh svojih zapadlih obveznosti (trajnejša nelikvidnost) ali če postane dolgoročno plačilno nesposoben.",
    },
    "ZFPPIPP:136": {
        "law": "ZFPPIPP",
        "number": "136",
        "title": "Prisilna poravnava",
        "content": "Dolžnik, ki je postal insolventen, lahko sodišču predlaga začetek postopka prisilne poravnave. V predlogu mora navesti ukrepe finančnega prestrukturiranja in roke za njihovo izvedbo.",
    },
    # --- ZDavP-2 ---
    "ZDavP-2:14": {
        "law": "ZDavP-2",
        "number": "14",
        "title": "Samoprijava",
        "content": "Davčni zavezanec, ki ni vložil davčne napovedi ali je v napovedi navedel neresnične ali nepopolne podatke, lahko vloži davčno napoved oziroma popravljeno davčno napoved najpozneje do vročitve odmerne odločbe ali do začetka davčnega inšpekcijskega nadzora.",
    },
    # --- ZPOmK-2 ---
    "ZPOmK-2:6": {
        "law": "ZPOmK-2",
        "number": "6",
        "title": "Prepovedani omejevalni sporazumi",
        "content": "Prepovedani so sporazumi med podjetji, sklepi podjetniških združenj in usklajena ravnanja, katerih cilj ali učinek je preprečevanje, omejevanje ali izkrivljanje konkurence, zlasti: neposredno ali posredno določanje cen, omejevanje proizvodnje, razdelitev trga.",
    },
    # --- ZArbit ---
    "ZArbit:10": {
        "law": "ZArbit",
        "number": "10",
        "title": "Arbitražni sporazum",
        "content": "Arbitražni sporazum je sporazum strank, da se obstoječ ali prihodnji spor iz določenega pravnega razmerja reši v arbitražnem postopku. Sporazum mora biti v pisni obliki.",
    },
    # --- ZBan-3 ---
    "ZBan-3:7": {
        "law": "ZBan-3",
        "number": "7",
        "title": "Bančne storitve",
        "content": "Bančne storitve so sprejemanje depozitov ali drugih vračljivih sredstev od javnosti in dajanje kreditov za svoj račun. Te storitve lahko opravlja le banka, ki je pridobila dovoljenje Banke Slovenije.",
    },
    # --- ZSReg ---
    "ZSReg:4": {
        "law": "ZSReg",
        "number": "4",
        "title": "Vpis v sodni register",
        "content": "V sodni register se vpišejo subjekti, ki jih je treba vpisati po zakonu: gospodarske družbe, podružnice, zadruge, zavodi, ustanove, politične stranke. Vpis je konstitutivne narave — pravna oseba nastane z vpisom.",
    },
}


# =============================================================================
# 2. COURT DECISIONS DATABASE — landmark rulings per field + keywords
#    Replaces: TFL GET /court-decisions
# =============================================================================

COURT_DECISIONS = {
    "VARSTVO OSEBNIH PODATKOV": [
        {
            "court": "Upravno sodišče RS",
            "case_number": "I U 1683/2019",
            "title": "Kršitev GDPR — nepriglasitev kršitve v 72 urah",
            "summary": "Sodišče je potrdilo globo Informacijskega pooblaščenca zaradi zamude pri priglasitvi kršitve. Upravljavec ni priglasil kršitve v 72 urah po odkritju.",
            "relevance_keywords": ["kršitev", "priglasitev", "72 ur", "globa", "informacijski pooblaščenec"],
            "key_articles": ["GDPR:33", "ZVOP-2:40"],
        },
        {
            "court": "Upravno sodišče RS",
            "case_number": "I U 444/2021",
            "title": "Obdelava osebnih podatkov brez pravne podlage",
            "summary": "Upravljavec je obdeloval osebne podatke zaposlenih brez ustrezne pravne podlage. Sodišče je potrdilo, da mora upravljavec za vsako obdelavo imeti jasno zakonsko podlago.",
            "relevance_keywords": ["obdelava", "pravna podlaga", "zaposleni", "privolitev"],
            "key_articles": ["GDPR:82", "GDPR:83"],
        },
    ],
    "DELOVNO PRAVO": [
        {
            "court": "Vrhovno sodišče RS",
            "case_number": "VIII Ips 206/2017",
            "title": "Nezakonita odpoved — kršitev postopka",
            "summary": "Vrhovno sodišče je ugotovilo, da je odpoved nezakonita, ker delodajalec ni izvedel zagovora delavca pred odpovedjo. Kršitev postopka iz čl. 89 ZDR-1 pomeni nezakonitost odpovedi.",
            "relevance_keywords": ["odpoved", "nezakonita", "zagovor", "postopek"],
            "key_articles": ["ZDR-1:83", "ZDR-1:89"],
        },
        {
            "court": "Vrhovno sodišče RS",
            "case_number": "VIII Ips 16/2019",
            "title": "Odpravnina — izračun osnove",
            "summary": "Sodišče je pojasnilo, da se v osnovo za izračun odpravnine vštevajo vsi dodatki k plači (regres, prevoz, prehrana) in ne le osnovna plača.",
            "relevance_keywords": ["odpravnina", "plača", "izračun", "odpoved", "poslovni razlog"],
            "key_articles": ["ZDR-1:108"],
        },
        {
            "court": "Višje delovno in socialno sodišče",
            "case_number": "Pdp 657/2020",
            "title": "Odpoved iz poslovnega razloga — fiktivnost",
            "summary": "Sodišče je ugotovilo, da je bil poslovni razlog fiktiven, saj je delodajalec takoj po odpovedi zaposlil novega delavca na isto delovno mesto. Odpoved je nezakonita.",
            "relevance_keywords": ["poslovni razlog", "fiktivnost", "reorganizacija", "odpoved"],
            "key_articles": ["ZDR-1:85"],
        },
        {
            "court": "Vrhovno sodišče RS",
            "case_number": "VIII Ips 278/2018",
            "title": "Zaščita žvižgača — povračilni ukrepi",
            "summary": "Odpoved delavcu, ki je prijavil nepravilnosti, je nezakonita kot povračilni ukrep. Sodišče je naložilo reintegracijo delavca.",
            "relevance_keywords": ["žvižgač", "prijavitelj", "povračilni", "nepravilnosti", "whistleblower"],
            "key_articles": ["ZZPri:7"],
        },
    ],
    "INTELEKTUALNA LASTNINA": [
        {
            "court": "Vrhovno sodišče RS",
            "case_number": "II Ips 201/2018",
            "title": "Avtorsko delo v delovnem razmerju — obseg prenosa pravic",
            "summary": "Sodišče je določilo, da se prenos avtorskih pravic na delodajalca nanaša le na dela, ki spadajo v okvir delovnih nalog zaposlenega. Izumi izven opisa del ostanejo last avtorja.",
            "relevance_keywords": ["avtorsko delo", "delovno razmerje", "programska oprema", "algoritem", "patent"],
            "key_articles": ["ZASP:101", "ZIL-1:18"],
        },
        {
            "court": "Višje sodišče v Ljubljani",
            "case_number": "I Cpg 542/2020",
            "title": "Kršitev licence — pogodbena kazen",
            "summary": "Licencojemalec je presegel dogovorjen obseg licence. Sodišče je prisodilo pogodbeno kazen in odškodnino za kršitev licenčne pogodbe.",
            "relevance_keywords": ["licenca", "kršitev", "programska oprema", "pogodbena kazen"],
            "key_articles": ["ZIL-1:67", "ZASP:80"],
        },
    ],
    "PREVZEMI IN ZDRUŽITVE": [
        {
            "court": "Vrhovno sodišče RS",
            "case_number": "III Ips 83/2019",
            "title": "Odgovornost za napačne zagotovila v SPA",
            "summary": "Prodajalec je v pogodbi o prodaji deleža dal napačna zagotovila (representations & warranties). Sodišče je prisodilo odškodnino kupcu na podlagi kršitve pogodbenih zagotovil.",
            "relevance_keywords": ["prevzem", "due diligence", "SPA", "zagotovila", "deleži", "M&A"],
            "key_articles": ["ZGD-1:529", "OZ:243"],
        },
        {
            "court": "Agencija za trg vrednostnih papirjev",
            "case_number": "Odločba ATVP 2020/34",
            "title": "Zamuda pri objavi prevzemne ponudbe",
            "summary": "ATVP je izdala globo ker prevzemnik ni v 30 dneh objavil prevzemne ponudbe po dosegu prevzemnega praga (1/3 glasovalnih pravic).",
            "relevance_keywords": ["prevzem", "prevzemna ponudba", "glasovalne pravice", "prag"],
            "key_articles": ["ZPre-1:12"],
        },
    ],
    "KORPORACIJSKO PRAVO": [
        {
            "court": "Vrhovno sodišče RS",
            "case_number": "III Ips 20/2020",
            "title": "Izstop družbenika iz d.o.o.",
            "summary": "Sodišče je obravnavalo zahtevo za izstop družbenika iz d.o.o. zaradi nezmožnosti soodločanja. Določen je bil postopek določitve odkupne vrednosti deleža.",
            "relevance_keywords": ["družbenik", "d.o.o.", "izstop", "delež", "ustanovitev"],
            "key_articles": ["ZGD-1:473", "ZGD-1:474"],
        },
    ],
    "KOMERCIALNE POGODBE": [
        {
            "court": "Vrhovno sodišče RS",
            "case_number": "II Ips 155/2019",
            "title": "Razveza pogodbe — bistvena kršitev",
            "summary": "Sodišče je potrdilo, da je upnik upravičen razvezati pogodbo brez dodatnega roka za izpolnitev, če je kršitev bistvena in jasna namera dolžnika, da ne bo izpolnil.",
            "relevance_keywords": ["pogodba", "razveza", "kršitev", "neizpolnitev", "odškodnina"],
            "key_articles": ["OZ:82", "OZ:243"],
        },
    ],
    "PREPREČEVANJE IN REŠEVANJE SPOROV": [
        {
            "court": "Vrhovno sodišče RS",
            "case_number": "II Ips 89/2021",
            "title": "Veljavnost arbitražne klavzule",
            "summary": "Sodišče je potrdilo veljavnost arbitražne klavzule v pogodbi, čeprav jo je šibkejša stranka izpodbijala. Arbitražni sporazum je veljaven, če je v pisni obliki.",
            "relevance_keywords": ["arbitraža", "klavzula", "spor", "tožba"],
            "key_articles": ["ZArbit:10"],
        },
    ],
}


# =============================================================================
# 3. CROSS-REFERENCES — which laws relate to each other
#    Replaces: TFL GET /legislation/{id}/references
# =============================================================================

LAW_CROSS_REFERENCES = {
    "ZGD-1": ["ZPre-1", "ZPOmK-2", "ZPPDFT-2", "ZSReg", "ZDavP-2"],
    "ZDR-1": ["ZZPri", "ZASP", "ZIL-1", "OZ"],
    "GDPR": ["ZVOP-2"],
    "ZVOP-2": ["GDPR"],
    "ZPPDFT-2": ["ZGD-1", "ZBan-3"],
    "ZPre-1": ["ZGD-1", "ZPOmK-2"],
    "ZASP": ["ZIL-1", "ZDR-1", "OZ"],
    "ZIL-1": ["ZASP", "OZ"],
    "OZ": ["ZPP", "ZDR-1", "ZGD-1"],
    "ZPP": ["OZ", "ZArbit"],
    "ZArbit": ["ZPP", "OZ"],
    "ZJN-3": ["ZPOmK-2", "ZPPDFT-2"],
    "SPZ": ["OZ", "GZ-1"],
    "GZ-1": ["SPZ"],
    "ZTuj-2": ["ZDR-1"],
    "ZFPPIPP": ["ZGD-1", "OZ"],
    "ZDavP-2": ["ZGD-1"],
    "ZBan-3": ["ZPPDFT-2", "ZGD-1"],
    "ZPOmK-2": ["ZGD-1", "ZPre-1"],
    "ZSReg": ["ZGD-1"],
    "ZZPri": ["ZDR-1"],
}


# =============================================================================
# 4. KEYWORD-TO-ARTICLE MAPPING — key_facts keywords → specific articles
#    Enhances field-based references with fact-specific legislation
# =============================================================================

KEYWORD_ARTICLE_MAP = {
    # Labor law keywords
    "odpoved": ["ZDR-1:83", "ZDR-1:89"],
    "odpravnina": ["ZDR-1:108"],
    "poslovni razlog": ["ZDR-1:85"],
    "krivdni razlog": ["ZDR-1:87"],
    "sodno varstvo": ["ZDR-1:200"],
    "tožba": ["ZPP:180", "ZDR-1:200"],
    "žvižgač": ["ZZPri:7"],
    "prijavitelj": ["ZZPri:7"],
    "whistleblower": ["ZZPri:7"],
    # IP keywords
    "patent": ["ZIL-1:10", "ZIL-1:18"],
    "licenca": ["ZIL-1:67"],
    "avtorsk": ["ZASP:5", "ZASP:80", "ZASP:101"],
    "programska oprema": ["ZASP:5", "ZASP:101"],
    "algoritem": ["ZASP:5", "ZIL-1:10"],
    "software": ["ZASP:5", "ZASP:101"],
    # Corporate keywords
    "d.o.o": ["ZGD-1:473", "ZGD-1:474"],
    "ustanovitev": ["ZGD-1:473", "ZSReg:4"],
    "registracija": ["ZGD-1:473", "ZSReg:4"],
    "podružnica": ["ZGD-1:680", "ZSReg:4"],
    "družbena pogodba": ["ZGD-1:474"],
    "družbenik": ["ZGD-1:473", "ZGD-1:474"],
    # M&A keywords
    "prevzem": ["ZPre-1:12", "ZGD-1:529"],
    "due diligence": ["ZGD-1:529"],
    "skrbni pregled": ["ZGD-1:529"],
    "združitev": ["ZGD-1:580"],
    "merger": ["ZGD-1:580"],
    "acquisition": ["ZPre-1:12", "ZGD-1:529"],
    "delež": ["ZGD-1:473"],
    # GDPR/data keywords
    "kršitev podatkov": ["GDPR:33", "GDPR:34", "ZVOP-2:40"],
    "osebni podatki": ["GDPR:82", "GDPR:83"],
    "priglasitev": ["GDPR:33", "ZVOP-2:40"],
    "data breach": ["GDPR:33", "GDPR:34"],
    "informacijski pooblaščenec": ["ZVOP-2:40", "ZVOP-2:102"],
    "globa": ["GDPR:83", "ZVOP-2:102"],
    # Contract keywords
    "pogodba": ["OZ:12", "OZ:82"],
    "razveza": ["OZ:82"],
    "odškodnina": ["OZ:243", "GDPR:82"],
    "neizpolnitev": ["OZ:82"],
    # AML keywords
    "pranje denarja": ["ZPPDFT-2:8", "ZPPDFT-2:68"],
    "dejanski lastnik": ["ZPPDFT-2:24"],
    "UBO": ["ZPPDFT-2:24"],
    "PEP": ["ZPPDFT-2:40"],
    "sankcije": ["ZPPDFT-2:42"],
    # Real estate keywords
    "nepremičnina": ["SPZ:37"],
    "zemljiška knjiga": ["SPZ:37"],
    "gradbeno dovoljenje": ["GZ-1:4"],
    # Migration keywords
    "dovoljenje za prebivanje": ["ZTuj-2:33"],
    "delovno dovoljenje": ["ZTuj-2:37"],
    # Insolvency keywords
    "stečaj": ["ZFPPIPP:14", "ZFPPIPP:231"],
    "prisilna poravnava": ["ZFPPIPP:136"],
    "insolventnost": ["ZFPPIPP:14"],
    # Dispute keywords
    "arbitraža": ["ZArbit:10"],
    "mediacija": ["ZPP:180"],
    # Public procurement
    "javno naročanje": ["ZJN-3:3", "ZJN-3:75"],
    "javni razpis": ["ZJN-3:3"],
    # Tax keywords
    "samoprijava": ["ZDavP-2:14"],
    "davčni inšpekcijski": ["ZDavP-2:14"],
    # Competition
    "kartel": ["ZPOmK-2:6"],
    "prevladujoči položaj": ["ZPOmK-2:9"],
}


# =============================================================================
# 5. CITATION EXTRACTION — regex detection of law references in text
#    Replaces: TFL POST /references/extract
# =============================================================================

# All known law abbreviations for regex matching
KNOWN_ABBREVIATIONS = [
    "GDPR", "ZVOP-2", "ZDR-1", "ZZPri", "ZGD-1", "ZPre-1", "ZIL-1", "ZASP",
    "ZPPDFT-2", "OZ", "ZPP", "ZArbit", "ZJN-3", "SPZ", "GZ-1", "ZTuj-2",
    "ZFPPIPP", "ZDavP-2", "ZPOmK-2", "ZBan-3", "ZSReg",
]


def extract_citations_from_text(text: str) -> list[dict]:
    """
    Scan raw text for legal citations like 'čl. 33 GDPR', '83. člen ZDR-1', 'Article 33 GDPR'.
    Returns list of detected citations with resolved article content.
    """
    citations = []
    seen = set()

    # Build abbreviation pattern
    abbr_pattern = "|".join(re.escape(a) for a in KNOWN_ABBREVIATIONS)

    # Patterns: "čl. 33 GDPR", "člen 83 ZDR-1", "33. člen GDPR"
    patterns = [
        rf'(?:čl\.|člen|členu|člena|article|art\.)\s*(\d+)\s*({abbr_pattern})',
        rf'(\d+)\.\s*(?:čl\.|člen|členu|člena)\s*({abbr_pattern})',
        rf'({abbr_pattern})\s*(?:čl\.|člen|členu|člena|,?\s*article|,?\s*art\.)\s*(\d+)',
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            groups = match.groups()
            if groups[0].isdigit():
                article_num = groups[0]
                law_abbr = groups[1]
            else:
                law_abbr = groups[0]
                article_num = groups[1]

            # Normalize abbreviation
            law_abbr_upper = law_abbr.upper()
            for known in KNOWN_ABBREVIATIONS:
                if known.upper() == law_abbr_upper:
                    law_abbr = known
                    break

            key = f"{law_abbr}:{article_num}"
            if key not in seen:
                seen.add(key)
                content = ARTICLE_CONTENT.get(key)
                citations.append({
                    "law": law_abbr,
                    "article": article_num,
                    "key": key,
                    "content": content.get("content") if content else None,
                    "title": content.get("title") if content else None,
                    "source": "email_citation",
                })

    # Also detect bare law mentions without article number
    for abbr in KNOWN_ABBREVIATIONS:
        if re.search(rf'\b{re.escape(abbr)}\b', text, re.IGNORECASE):
            key = f"law:{abbr}"
            if key not in seen:
                seen.add(key)
                citations.append({
                    "law": abbr,
                    "article": None,
                    "key": key,
                    "content": None,
                    "title": f"Omemba zakona {abbr}",
                    "source": "email_mention",
                })

    return citations


# =============================================================================
# 6. FIELD → LEGISLATION MAPPING (existing, enhanced with article content)
# =============================================================================

FIELD_LEGISLATION = {
    "VARSTVO OSEBNIH PODATKOV": [
        {
            "law": "Splošna uredba o varstvu podatkov (GDPR)",
            "abbreviation": "GDPR",
            "articles": [
                {"number": "33", "title": "Priglasitev kršitve varstva osebnih podatkov nadzornemu organu", "note": "72-urni rok za priglasitev"},
                {"number": "34", "title": "Sporočanje kršitve varstva osebnih podatkov posamezniku"},
                {"number": "82", "title": "Pravica do odškodnine in odgovornost"},
                {"number": "83", "title": "Splošni pogoji za naložitev upravnih glob"},
            ],
        },
        {
            "law": "Zakon o varstvu osebnih podatkov (ZVOP-2)",
            "abbreviation": "ZVOP-2",
            "articles": [
                {"number": "40", "title": "Priglasitev kršitve Informacijskemu pooblaščencu"},
                {"number": "41", "title": "Obveščanje posameznikov o kršitvi"},
                {"number": "102", "title": "Globe za kršitve"},
            ],
        },
    ],
    "DELOVNO PRAVO": [
        {
            "law": "Zakon o delovnih razmerjih (ZDR-1)",
            "abbreviation": "ZDR-1",
            "articles": [
                {"number": "83", "title": "Razlogi za redno odpoved pogodbe o zaposlitvi"},
                {"number": "85", "title": "Odpoved iz poslovnega razloga"},
                {"number": "87", "title": "Odpoved iz krivdnega razloga"},
                {"number": "89", "title": "Postopek pred redno odpovedjo"},
                {"number": "200", "title": "Sodno varstvo — roki za vložitev tožbe"},
            ],
        },
        {
            "law": "Zakon o zaščiti prijaviteljev (ZZPri)",
            "abbreviation": "ZZPri",
            "articles": [
                {"number": "7", "title": "Prepoved povračilnih ukrepov"},
                {"number": "18", "title": "Notranja pot za prijavo"},
                {"number": "26", "title": "Pravno varstvo prijavitelja"},
            ],
        },
    ],
    "INTELEKTUALNA LASTNINA": [
        {
            "law": "Zakon o industrijski lastnini (ZIL-1)",
            "abbreviation": "ZIL-1",
            "articles": [
                {"number": "10", "title": "Pogoji za patentiranje izuma"},
                {"number": "18", "title": "Pravica do patenta"},
                {"number": "67", "title": "Licenčna pogodba"},
            ],
        },
        {
            "law": "Zakon o avtorski in sorodnih pravicah (ZASP)",
            "abbreviation": "ZASP",
            "articles": [
                {"number": "5", "title": "Avtorsko delo — programska oprema"},
                {"number": "101", "title": "Avtorsko delo, ustvarjeno v delovnem razmerju"},
                {"number": "80", "title": "Prenos materialnih avtorskih pravic"},
            ],
        },
    ],
    "PREVZEMI IN ZDRUŽITVE": [
        {
            "law": "Zakon o gospodarskih družbah (ZGD-1)",
            "abbreviation": "ZGD-1",
            "articles": [
                {"number": "580", "title": "Združitev (merger) — splošne določbe"},
                {"number": "435", "title": "Pridobitev lastnih poslovnih deležev"},
                {"number": "529", "title": "Skrbni pregled (due diligence)"},
            ],
        },
        {
            "law": "Zakon o prevzemih (ZPre-1)",
            "abbreviation": "ZPre-1",
            "articles": [
                {"number": "12", "title": "Obveznost prevzemne ponudbe"},
                {"number": "32", "title": "Prevzemna cena"},
            ],
        },
    ],
    "KORPORACIJSKO PRAVO": [
        {
            "law": "Zakon o gospodarskih družbah (ZGD-1)",
            "abbreviation": "ZGD-1",
            "articles": [
                {"number": "3", "title": "Vrste gospodarskih družb"},
                {"number": "473", "title": "Ustanovitev družbe z omejeno odgovornostjo (d.o.o.)"},
                {"number": "474", "title": "Družbena pogodba"},
                {"number": "680", "title": "Podružnice tujih podjetij"},
            ],
        },
        {
            "law": "Zakon o sodnem registru (ZSReg)",
            "abbreviation": "ZSReg",
            "articles": [
                {"number": "4", "title": "Vpis v sodni register"},
            ],
        },
    ],
    "BANČNIŠTVO IN FINANCE": [
        {
            "law": "Zakon o bančništvu (ZBan-3)",
            "abbreviation": "ZBan-3",
            "articles": [
                {"number": "7", "title": "Bančne storitve"},
                {"number": "150", "title": "Upravljanje tveganj"},
            ],
        },
    ],
    "DAVČNO PRAVO": [
        {
            "law": "Zakon o davčnem postopku (ZDavP-2)",
            "abbreviation": "ZDavP-2",
            "articles": [
                {"number": "14", "title": "Samoprijava"},
                {"number": "68", "title": "Odmera davka"},
            ],
        },
    ],
    "KONKURENČNO PRAVO": [
        {
            "law": "Zakon o preprečevanju omejevanja konkurence (ZPOmK-2)",
            "abbreviation": "ZPOmK-2",
            "articles": [
                {"number": "6", "title": "Prepovedani omejevalni sporazumi"},
                {"number": "9", "title": "Zloraba prevladujočega položaja"},
            ],
        },
    ],
    "KOMERCIALNE POGODBE": [
        {
            "law": "Obligacijski zakonik (OZ)",
            "abbreviation": "OZ",
            "articles": [
                {"number": "12", "title": "Svoboda urejanja obligacijskih razmerij"},
                {"number": "82", "title": "Razveza pogodbe"},
                {"number": "243", "title": "Odškodninska odgovornost"},
            ],
        },
    ],
    "PREPREČEVANJE IN REŠEVANJE SPOROV": [
        {
            "law": "Zakon o pravdnem postopku (ZPP)",
            "abbreviation": "ZPP",
            "articles": [
                {"number": "11", "title": "Krajevna pristojnost"},
                {"number": "180", "title": "Tožba"},
            ],
        },
        {
            "law": "Zakon o arbitraži (ZArbit)",
            "abbreviation": "ZArbit",
            "articles": [
                {"number": "10", "title": "Arbitražni sporazum"},
            ],
        },
    ],
    "JAVNO NAROČANJE": [
        {
            "law": "Zakon o javnem naročanju (ZJN-3)",
            "abbreviation": "ZJN-3",
            "articles": [
                {"number": "3", "title": "Temeljna načela"},
                {"number": "75", "title": "Razlogi za izključitev"},
            ],
        },
    ],
    "NEPREMIČNINE, GRADBENIŠTVO IN INFRASTRUKTURA": [
        {
            "law": "Stvarnopravni zakonik (SPZ)",
            "abbreviation": "SPZ",
            "articles": [
                {"number": "37", "title": "Pridobitev lastninske pravice na nepremičnini"},
            ],
        },
        {
            "law": "Gradbeni zakon (GZ-1)",
            "abbreviation": "GZ-1",
            "articles": [
                {"number": "4", "title": "Gradbeno dovoljenje"},
            ],
        },
    ],
    "MIGRACIJSKO PRAVO": [
        {
            "law": "Zakon o tujcih (ZTuj-2)",
            "abbreviation": "ZTuj-2",
            "articles": [
                {"number": "33", "title": "Dovoljenje za prebivanje"},
                {"number": "37", "title": "Enotno dovoljenje za prebivanje in delo"},
            ],
        },
    ],
    "INSOLVENČNO PRAVO IN PRESTRUKTURIRANJA": [
        {
            "law": "Zakon o finančnem poslovanju, postopkih zaradi insolventnosti in prisilnem prenehanju (ZFPPIPP)",
            "abbreviation": "ZFPPIPP",
            "articles": [
                {"number": "14", "title": "Insolventnost"},
                {"number": "136", "title": "Prisilna poravnava"},
                {"number": "231", "title": "Stečajni postopek"},
            ],
        },
    ],
}

# AML-specific legislation
AML_LEGISLATION = [
    {
        "law": "Zakon o preprečevanju pranja denarja in financiranja terorizma (ZPPDFT-2)",
        "abbreviation": "ZPPDFT-2",
        "articles": [
            {"number": "8", "title": "Ocena tveganja s strani zavezanca"},
            {"number": "16", "title": "Pregled stranke — ukrepi"},
            {"number": "24", "title": "Ugotavljanje dejanskega lastnika"},
            {"number": "37", "title": "Poenostavljen pregled stranke (nizko tveganje)"},
            {"number": "38", "title": "Poglobljen pregled stranke (visoko tveganje)"},
            {"number": "68", "title": "Poročanje o sumljivih transakcijah"},
            {"number": "137", "title": "Globe za kršitve"},
        ],
    },
]

AML_INDICATOR_ARTICLES = {
    "high_risk_jurisdiction": {
        "law": "ZPPDFT-2",
        "article": "42",
        "title": "Tretje države z visokim tveganjem — poglobljen pregled",
    },
    "pep_involved": {
        "law": "ZPPDFT-2",
        "article": "40",
        "title": "Politično izpostavljene osebe — dodatni ukrepi",
    },
    "complex_ownership": {
        "law": "ZPPDFT-2",
        "article": "24",
        "title": "Ugotavljanje dejanskega lastnika (UBO)",
    },
    "opaque_fund_source": {
        "law": "ZPPDFT-2",
        "article": "38",
        "title": "Poglobljen pregled stranke — izvor sredstev",
    },
}

DEADLINE_LEGISLATION = {
    "GDPR": {
        "law": "GDPR čl. 33",
        "note": "72 ur za priglasitev kršitve nadzornemu organu od odkritja",
    },
    "priglasitev": {
        "law": "ZVOP-2 čl. 40",
        "note": "Priglasitev Informacijskemu pooblaščencu RS",
    },
}


# =============================================================================
# 7. MAIN FUNCTION — combines all features into unified legal references
# =============================================================================

def get_legal_references(
    field: str,
    aml_indicators: dict | None = None,
    aml_risk: str = "GREEN",
    raw_email: str = "",
    key_facts: list[str] | None = None,
) -> dict:
    """
    Mini-TFL: Return comprehensive legal intelligence using only internal features.

    Returns dict with:
    - legislation: field-based laws + articles (with content)
    - citations: law references detected in raw email
    - court_decisions: relevant landmark rulings
    - cross_references: related laws
    - keyword_articles: additional articles triggered by key_facts
    """
    result = {
        "legislation": [],
        "citations": [],
        "court_decisions": [],
        "cross_references": {},
        "keyword_articles": [],
    }

    # --- 1. Field-based legislation (existing) ---
    field_laws = FIELD_LEGISLATION.get(field, [])
    for law in field_laws:
        # Enrich articles with content
        enriched_articles = []
        for art in law.get("articles", []):
            key = f"{law['abbreviation']}:{art['number']}"
            content = ARTICLE_CONTENT.get(key)
            enriched = {**art}
            if content:
                enriched["content"] = content.get("content", "")
                if content.get("deadline"):
                    enriched["deadline"] = content["deadline"]
                if content.get("note"):
                    enriched["note"] = content.get("note", enriched.get("note", ""))
            enriched_articles.append(enriched)
        result["legislation"].append({
            **law,
            "articles": enriched_articles,
        })

    # --- 2. AML legislation ---
    if aml_risk in ("ORANGE", "RED") or (aml_indicators and any(aml_indicators.values())):
        for law in AML_LEGISLATION:
            enriched_articles = []
            for art in law.get("articles", []):
                key = f"{law['abbreviation']}:{art['number']}"
                content = ARTICLE_CONTENT.get(key)
                enriched = {**art}
                if content:
                    enriched["content"] = content.get("content", "")
                enriched_articles.append(enriched)
            result["legislation"].append({**law, "articles": enriched_articles})

        # Specific AML indicator articles
        if aml_indicators:
            extra_articles = []
            for indicator, flagged in aml_indicators.items():
                if flagged and indicator in AML_INDICATOR_ARTICLES:
                    extra = AML_INDICATOR_ARTICLES[indicator]
                    key = f"{extra['law']}:{extra['article']}"
                    content = ARTICLE_CONTENT.get(key)
                    art_entry = {
                        "number": extra["article"],
                        "title": f"{extra['title']} (indicator: {indicator})",
                    }
                    if content:
                        art_entry["content"] = content.get("content", "")
                    extra_articles.append(art_entry)
            if extra_articles:
                result["legislation"].append({
                    "law": "ZPPDFT-2 — specifični členi glede na indikatorje",
                    "abbreviation": "ZPPDFT-2",
                    "articles": extra_articles,
                })

    # --- 3. Citation extraction from raw email ---
    if raw_email:
        result["citations"] = extract_citations_from_text(raw_email)

    # --- 4. Court decisions based on field + key_facts ---
    field_decisions = COURT_DECISIONS.get(field, [])
    if key_facts and field_decisions:
        # Score decisions by keyword overlap with key_facts
        facts_text = " ".join(key_facts).lower()
        scored = []
        for decision in field_decisions:
            score = sum(1 for kw in decision["relevance_keywords"] if kw in facts_text)
            scored.append((score, decision))
        # Return all field decisions, sorted by relevance
        scored.sort(key=lambda x: x[0], reverse=True)
        result["court_decisions"] = [d for _, d in scored]
    else:
        result["court_decisions"] = field_decisions

    # --- 5. Cross-references ---
    seen_laws = set()
    for law in result["legislation"]:
        abbr = law.get("abbreviation", "")
        if abbr:
            seen_laws.add(abbr)
            refs = LAW_CROSS_REFERENCES.get(abbr, [])
            if refs:
                result["cross_references"][abbr] = refs

    # --- 6. Keyword-to-article mapping from key_facts ---
    if key_facts:
        facts_text = " ".join(key_facts).lower()
        already_referenced = set()
        for law in result["legislation"]:
            for art in law.get("articles", []):
                already_referenced.add(f"{law['abbreviation']}:{art['number']}")

        keyword_hits = []
        seen_keys = set()
        for keyword, article_keys in KEYWORD_ARTICLE_MAP.items():
            if keyword.lower() in facts_text:
                for key in article_keys:
                    if key not in already_referenced and key not in seen_keys:
                        seen_keys.add(key)
                        content = ARTICLE_CONTENT.get(key)
                        if content:
                            keyword_hits.append({
                                "key": key,
                                "law": content["law"],
                                "number": content["number"],
                                "title": content["title"],
                                "content": content.get("content", ""),
                                "triggered_by": keyword,
                            })
        result["keyword_articles"] = keyword_hits

    return result
