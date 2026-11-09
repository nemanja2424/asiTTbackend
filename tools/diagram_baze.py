"""Generate the editable SVG overview of the PostgreSQL business schema."""
from html import escape
from pathlib import Path


OUT = Path(__file__).with_name("diagram_baze.svg")
W, H = 1600, 1160
pieces = [f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="title desc">
<title id="title">timeTracker — dijagram baze podataka</title>
<desc id="desc">Sedam poslovnih tabela: users, departments, projects, logs i tri spojne tabele za članstva i dodele. Prikazani su primarni i strani ključevi.</desc>
<defs>
  <style>
    text {{ font-family: Arial, Helvetica, sans-serif; fill: #17324d; }}
    .title {{ font-size: 34px; font-weight: 700; }}
    .subtitle {{ font-size: 17px; fill: #58708a; }}
    .name {{ font-size: 22px; font-weight: 700; fill: white; }}
    .kind {{ font-size: 14px; fill: #e9f2fb; }}
    .row {{ font-size: 16px; }}
    .type {{ font-size: 13px; fill: #6a7d90; }}
    .key {{ font-size: 12px; font-weight: 700; fill: #145c6b; }}
    .caption {{ font-size: 14px; fill: #506780; }}
    .edge {{ fill: none; stroke: #5b7892; stroke-width: 2.5; stroke-linecap: round; stroke-linejoin: round; }}
    .optional {{ stroke-dasharray: 7 6; }}
    .many {{ fill: #ffffff; stroke: #5b7892; stroke-width: 2; }}
  </style>
  <filter id="shadow" x="-10%" y="-10%" width="120%" height="130%"><feDropShadow dx="0" dy="4" stdDeviation="6" flood-color="#1c3b58" flood-opacity="0.10"/></filter>
</defs>
<rect width="1600" height="1160" fill="#f4f8fc"/>
<text x="68" y="70" class="title">timeTracker · baza podataka</text>
<text x="68" y="102" class="subtitle">PostgreSQL 18 · poslovne tabele, ključevi i odnosi</text>
''']


def edge(points, dashed=False):
    cls = "edge optional" if dashed else "edge"
    pieces.append(f'<polyline class="{cls}" points="{points}"/>')


def label(x, y, s):
    pieces.append(f'<text x="{x}" y="{y}" class="caption">{escape(s)}</text>')


def card(x, y, w, title, kind, accent, fields):
    header = 66
    row_h = 31
    height = header + 16 + len(fields) * row_h + 12
    pieces.append(f'<rect x="{x}" y="{y}" width="{w}" height="{height}" rx="14" fill="white" stroke="#d5e0ea" filter="url(#shadow)"/>')
    pieces.append(f'<path d="M{x+14},{y} H{x+w-14} Q{x+w},{y} {x+w},{y+14} V{y+66} H{x} V{y+14} Q{x},{y} {x+14},{y}" fill="{accent}"/>')
    pieces.append(f'<text x="{x+20}" y="{y+30}" class="name">{escape(title)}</text>')
    pieces.append(f'<text x="{x+20}" y="{y+52}" class="kind">{escape(kind)}</text>')
    for i, (name, typ, key) in enumerate(fields):
        ry = y + header + 30 + i * row_h
        if i % 2 == 0:
            pieces.append(f'<rect x="{x+1}" y="{ry-22}" width="{w-2}" height="{row_h}" fill="#f7fafc"/>')
        pieces.append(f'<text x="{x+20}" y="{ry}" class="row">{escape(name)}</text>')
        if key:
            pieces.append(f'<text x="{x+w-100}" y="{ry}" class="key">{key}</text>')
        pieces.append(f'<text x="{x+w-20}" y="{ry}" class="type" text-anchor="end">{escape(typ)}</text>')
    return height


# Orthogonal links sit behind the table cards.
edge("390,264 480,264")                            # users -> user_departments
edge("800,264 1030,264 1030,325 1110,325")      # user_departments -> departments
edge("210,522 210,666")                          # users -> logs
edge("390,458 590,458 590,735 790,735")        # users -> project_users
edge("1290,190 1290,150 1450,150 1450,190", True)  # department parent
edge("1180,190 1180,133 210,133 210,190", True)    # manager -> user
edge("1110,490 1100,490 1100,540 1090,540")    # departments -> project_departments
edge("1090,565 1100,565 1100,716 1110,716")    # project_departments -> projects
edge("1090,735 1110,735")                         # project_users -> projects
edge("390,863 620,863 620,1085 1290,1085 1290,1000")  # logs -> projects

card(70, 190, 320, "users", "Korisnici", "#235b81", [
    ("id", "UUID", "PK"), ("email", "TEXT", ""),
    ("password_hash", "TEXT", ""), ("full_name", "TEXT", ""),
    ("role", "TEXT", ""), ("is_active", "BOOL", ""),
    ("last_active_at", "TIMESTAMPTZ", ""),
    ("created_at", "TIMESTAMPTZ", ""), ("updated_at", "TIMESTAMPTZ", ""),
])
card(480, 190, 320, "user_departments", "Članstva", "#387b91", [
    ("user_id", "UUID", "PK·FK"), ("department_id", "UUID", "PK·FK"),
])
card(1110, 190, 390, "departments", "Hijerarhija odeljenja", "#235b81", [
    ("id", "UUID", "PK"), ("name", "TEXT", ""),
    ("description", "TEXT", ""), ("parent_department_id", "UUID", "FK"),
    ("manager_id", "UUID", "FK"), ("is_active", "BOOL", ""),
    ("created_at", "TIMESTAMPTZ", ""), ("updated_at", "TIMESTAMPTZ", ""),
])
card(790, 500, 300, "project_departments", "Dodela odeljenja", "#387b91", [
    ("project_id", "UUID", "PK·FK"), ("department_id", "UUID", "PK·FK"),
])
card(790, 690, 300, "project_users", "Dodatni učesnici", "#387b91", [
    ("project_id", "UUID", "PK·FK"), ("user_id", "UUID", "PK·FK"),
])
card(70, 666, 320, "logs", "Završeni zapisi rada", "#235b81", [
    ("id", "UUID", "PK"), ("user_id", "UUID", "FK"),
    ("project_id", "UUID", "FK"), ("start_time", "TIMESTAMPTZ", ""),
    ("end_time", "TIMESTAMPTZ", ""), ("spent_time", "BIGINT", ""),
    ("note", "TEXT", ""), ("created_at", "TIMESTAMPTZ", ""),
    ("updated_at", "TIMESTAMPTZ", ""),
])
card(1110, 670, 390, "projects", "Projekti", "#235b81", [
    ("id", "UUID", "PK"), ("name", "TEXT", ""),
    ("description", "TEXT", ""), ("status", "TEXT", ""),
    ("start_date", "DATE", ""), ("end_date", "DATE", ""),
    ("archived_at", "TIMESTAMPTZ", ""),
    ("created_at", "TIMESTAMPTZ", ""), ("updated_at", "TIMESTAMPTZ", ""),
])

label(226, 628, "1 → više")
label(1280, 140, "parent_department_id")
label(682, 125, "manager_id → users.id")
label(480, 442, "direktna dodela korisnika")
label(630, 1067, "logs.project_id → projects.id")
pieces.append('''<rect x="70" y="1110" width="1430" height="32" rx="8" fill="#e7eff6"/>
<text x="85" y="1131" class="caption">PK = primarni ključ · FK = strani ključ · puna linija = obavezna veza · isprekidana = opciona veza · pomoćna tabela department_hierarchy_guard nije prikazana</text>
</svg>''')
OUT.write_text("\n".join(pieces), encoding="utf-8")
print(OUT)
