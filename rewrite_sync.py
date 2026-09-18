with open("skills/asana-obsidian-llm-wiki/scripts/asana_obsidian_sync.py", "r") as f:
    text = f.read()

# Replace 1: signature and active_ws
sig_old = """def plan_sync(token, vault, workspace_gid=None, project_limit=None):
    \"\"\"Compute the full plan. Returns (plan, meta). Writes nothing.\"\"\"
    now = datetime.now().astimezone().replace(microsecond=0)
    synced_at = now.isoformat()

    workspaces = fetch_workspaces(token)
    if not workspaces:
        raise AsanaError("No workspaces returned for this token.")

    ws = None
    if workspace_gid:
        ws = next((w for w in workspaces if w["gid"] == workspace_gid), None)
    ws = ws or workspaces[0]

    teams = fetch_teams(token, ws["gid"])
    projects = fetch_projects(token, ws["gid"], limit=project_limit)

    # Capa Programa: Portfolios nativos si el tier lo permite; si no (402/403),
    # program_map queda vacío y cada proyecto cae en el bucket genérico salvo
    # override manual.
    me = fetch_me(token)
    portfolios = fetch_portfolios(token, ws["gid"], me.get("gid"))
    portfolios_available = portfolios is not None
    program_map = build_program_map(token, portfolios) if portfolios else {}

    existing = scan_existing_notes(vault)

    plan = {"create": [], "update": [], "skip": [], "corrupt": [], "people_stats": {}}
    programs_seen = set()
    for p in projects:
        gid = p["gid"]
        tasks = fetch_project_tasks(token, gid)
        note_name = slugify(p.get("name"), fallback_gid=gid)
        ws_name = ws.get("name")"""

sig_new = """def plan_sync(token, vault, target_workspaces=None, all_workspaces=False, project_limit=None):
    \"\"\"Compute the full plan. Returns (plan, meta). Writes nothing.\"\"\"
    now = datetime.now().astimezone().replace(microsecond=0)
    synced_at = now.isoformat()

    workspaces = fetch_workspaces(token)
    if not workspaces:
        raise AsanaError("No workspaces returned for this token.")

    if target_workspaces:
        active_ws = [w for w in workspaces if w["gid"] in target_workspaces]
        if not active_ws:
            raise AsanaError("None of the provided workspace GIDs were found.")
    elif all_workspaces:
        active_ws = workspaces
    else:
        active_ws = [workspaces[0]]

    me = fetch_me(token)

    plan = {"create": [], "update": [], "skip": [], "corrupt": [], "people_stats": {}}
    programs_seen = set()
    
    meta = {
        "teams": [],
        "projects": [],
        "portfolios_available": False,
        "programs": [],
        "existing_count": 0,
        "synced_at": synced_at,
        "workspaces": active_ws
    }
    
    existing = scan_existing_notes(vault)
    meta["existing_count"] = len(existing)

    for ws in active_ws:
        teams = fetch_teams(token, ws["gid"])
        meta["teams"].extend(teams)
        
        projects = fetch_projects(token, ws["gid"], limit=project_limit)
        meta["projects"].extend(projects)
        
        portfolios = fetch_portfolios(token, ws["gid"], me.get("gid"))
        if portfolios is not None:
            meta["portfolios_available"] = True
        program_map = build_program_map(token, portfolios) if portfolios else {}

        for p in projects:
            gid = p["gid"]
            tasks = fetch_project_tasks(token, gid)
            note_name = slugify(p.get("name"), fallback_gid=gid)
            ws_name = ws.get("name")"""

text = text.replace(sig_old, sig_new)


# Replace 2: frontmatter workspace injection for create
fm_create_old = """        fm = {
            "type": "proyecto",
            "programa": override_prog or pg,
            "status": p.get("color") or "none",
            "asana_gid": gid,
            "due_date": override_due or orig_due,
            "rag_declarado": override_rag,
            "_title": p.get("name")
        }"""
fm_create_new = """        fm = {
            "type": "proyecto",
            "workspace": ws_name,
            "programa": override_prog or pg,
            "status": p.get("color") or "none",
            "asana_gid": gid,
            "due_date": override_due or orig_due,
            "rag_declarado": override_rag,
            "_title": p.get("name")
        }"""
# Only replace the first occurrence (which is the one inside `if not ex:`)
text = text.replace(fm_create_old, fm_create_new, 1)

# Replace 3: frontmatter workspace injection for update
fm_update_old = """        fm = {
            "type": old_fm.get("type", "proyecto"),
            "programa": override_prog or pg,
            "status": p.get("color") or "none",
            "asana_gid": gid,
            "due_date": override_due or orig_due,
            "rag_declarado": override_rag,
            "_title": p.get("name")
        }"""
fm_update_new = """        fm = {
            "type": old_fm.get("type", "proyecto"),
            "workspace": ws_name,
            "programa": override_prog or pg,
            "status": p.get("color") or "none",
            "asana_gid": gid,
            "due_date": override_due or orig_due,
            "rag_declarado": override_rag,
            "_title": p.get("name")
        }"""
text = text.replace(fm_update_old, fm_update_new)


# Replace 4: meta at bottom of plan_sync
meta_old = """    meta = {
        "workspace": ws,
        "teams": teams,
        "projects": projects,
        "portfolios_available": portfolios_available,
        "programs": sorted(list(programs_seen)),
        "existing_count": len(existing),
        "synced_at": synced_at
    }
    return plan, meta"""
meta_new = """    meta["programs"] = sorted(list(programs_seen))
    return plan, meta"""
text = text.replace(meta_old, meta_new)


# Replace 5: argparse main function
main_old = """    ap.add_argument("--workspace", metavar="GID", help="force a workspace gid")
    ap.add_argument("--limit", type=int, default=None, help="max projects (default None/all)")
    ap.add_argument("--record-deletion", metavar="PROJECT_GID",
                    help="record a deleted task in a project note")
    ap.add_argument("--task-name", metavar="NAME",
                    help="name of the deleted task (with --record-deletion)")
    ap.add_argument("--task-gid", metavar="GID",
                    help="gid of the deleted task (with --record-deletion)")
    args = ap.parse_args()

    token, vault = load_env()
    if not vault or not os.path.isdir(vault):
        print("ERROR: OBSIDIAN_VAULT_PATH inválido o inaccesible: %r" % vault)
        return 2

    if args.record_deletion:
        if not args.task_name:
            print("ERROR: --record-deletion requiere --task-name")
            return 2
        return record_deletion(vault, args.record_deletion, args.task_name,
                               args.task_gid or "desconocido", apply=args.apply)

    if not token:
        print("ERROR: ASANA_ACCESS_TOKEN vacío en .env. Pega el token y reintenta.")
        return 2

    try:
        if args.query:
            cmd_query(token, vault, args.query)
            return 0

        plan, meta = plan_sync(token, vault, args.workspace, args.limit)
    except AsanaError as e:
        print("ERROR de Asana: %s" % e)
        print("No se modificó nada en Obsidian.")
        return 1

    ws = meta["workspace"]
    print("Workspace : %s (%s)" % (ws.get("name"), ws["gid"]))"""
main_new = """    ap.add_argument("--workspace", metavar="GID", nargs="+", help="force specific workspace gid(s)")
    ap.add_argument("--all-workspaces", action="store_true", help="sync all available workspaces")
    ap.add_argument("--limit", type=int, default=None, help="max projects per workspace (default None/all)")
    ap.add_argument("--record-deletion", metavar="PROJECT_GID",
                    help="record a deleted task in a project note")
    ap.add_argument("--task-name", metavar="NAME",
                    help="name of the deleted task (with --record-deletion)")
    ap.add_argument("--task-gid", metavar="GID",
                    help="gid of the deleted task (with --record-deletion)")
    args = ap.parse_args()

    token, vault = load_env()
    if not vault or not os.path.isdir(vault):
        print("ERROR: OBSIDIAN_VAULT_PATH inválido o inaccesible: %r" % vault)
        return 2

    if args.record_deletion:
        if not args.task_name:
            print("ERROR: --record-deletion requiere --task-name")
            return 2
        return record_deletion(vault, args.record_deletion, args.task_name,
                               args.task_gid or "desconocido", apply=args.apply)

    if not token:
        print("ERROR: ASANA_ACCESS_TOKEN vacío en .env. Pega el token y reintenta.")
        return 2

    try:
        if args.query:
            cmd_query(token, vault, args.query)
            return 0

        plan, meta = plan_sync(token, vault, args.workspace, args.all_workspaces, args.limit)
    except AsanaError as e:
        print("ERROR de Asana: %s" % e)
        print("No se modificó nada en Obsidian.")
        return 1

    ws_names = [w.get("name") for w in meta["workspaces"]]
    print("Workspaces: %s" % (", ".join(ws_names)))"""
text = text.replace(main_old, main_new)


with open("skills/asana-obsidian-llm-wiki/scripts/asana_obsidian_sync.py", "w") as f:
    f.write(text)
