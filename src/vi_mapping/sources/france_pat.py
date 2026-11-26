"""Projets alimentaires territoriaux (PAT) franciliens et lauréats de l'appel à projets du PNA.

Le porteur, le service chargé du PAT, son téléphone et son site sont gardés ; le fichier ne donne pas d'e-mail.
"""

from __future__ import annotations

import csv
import io
import re
import sys

from ..db import upsert
from ..outils.datagouv import derniere
from ..outils.texte import normaliser, propre, sans_contact, site_web, telephone
from .base import Compteurs, Contexte, connecteur

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))
JEU = "6602f669c57897579c1a37ec"


def niveau_num(texte: str | None) -> int | None:
    """« Labellisation Niveau 2 » -> 2 ; un PAT reconnu sans niveau précisé -> None."""
    m = re.search(r"niveau\s*([12])", texte or "", re.I)
    return int(m.group(1)) if m else None


@connecteur("france_pat", depend_de=["ign_admin_express"])
def collecter(ctx: Contexte) -> Compteurs:
    ressource = derniere(ctx.http, JEU, r"pats-\d{8}\.csv")
    texte = ctx.http.get(ressource.url).content.decode("utf-8-sig")
    communes_idf = {r["code_insee"] for r in ctx.conn.execute("SELECT code_insee FROM commune")}
    lignes = []
    for p in csv.DictReader(io.StringIO(texte), delimiter=";"):
        perimetre = sorted({c.strip() for c in p["communes_code_insee"].split(",")} & communes_idf)
        if not perimetre:
            continue
        annee = p["annee_dobtention_de_la_derniere_labellisation"].strip()
        commun = {
            "nom": propre(p["nom_usuel"]) or propre(p["nom_administratif"]) or f"PAT {p['id']}",
            "communes": perimetre,
            "axe_education_alimentaire": "education alimentaire" in normaliser(p["axes_thematiques"]),
            "annee": int(annee) if annee.isdigit() else None,
            "niveau": propre(p["niveaux_de_labelisation"]),
            "niveau_num": niveau_num(p["niveaux_de_labelisation"]),
            "porteur": sans_contact(p.get("contact_structure")) or sans_contact(p.get("porteur_point_dentree_du_pat")),
            "service": sans_contact(p.get("contact_nom_du_service")),
            "telephone": telephone(p.get("contact_telephone")),
            "site_web": site_web(p.get("lien_vers_le_site_du_pat")) or site_web(
                p.get("lien_vers_le_site_du_porteur")),
            **ctx.provenance(p["lien_vers_la_fiche_pat"].strip() or ressource.url),
        }
        lignes.append({"id": f"pat:{p['id']}", "type": "pat", **commun})
        if normaliser(p["laureat_du_aap_pna"]) == "oui":
            lignes.append({"id": f"laureat_aap:{p['id']}", "type": "laureat_aap", **commun})
    n = upsert(ctx.conn, "dispositif", lignes, ["id"])
    ctx.conn.execute(
        "UPDATE dispositif d SET geom = (SELECT ST_Multi(ST_Union(c.geom)) FROM commune c "
        "WHERE c.code_insee = ANY(d.communes)) WHERE d.source = %s", (ctx.code,)
    )
    return {
        "pat": sum(ligne["type"] == "pat" for ligne in lignes),
        "pat_avec_axe_education": sum(
            ligne["type"] == "pat" and ligne["axe_education_alimentaire"] for ligne in lignes),
        "laureats_aap": sum(ligne["type"] == "laureat_aap" for ligne in lignes), "ecrits": n,
        "supprimes": ctx.purger("dispositif"),
    }
