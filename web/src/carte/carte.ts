/** Carte MapLibre : fond IGN, couches, survol, clic, sélection. */

import 'maplibre-gl/dist/maplibre-gl.css';

import type { Feature, FeatureCollection, LineString, Point } from 'geojson';
import {
  AttributionControl, GeoJSONSource, Map as CarteGL, NavigationControl, Popup, ScaleControl, setWorkerUrl,
  type MapGeoJSONFeature, type MapMouseEvent,
} from 'maplibre-gl';
import urlWorker from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';

import { adresse, chargerPats, chargerZone } from '../donnees';
import { COUCHES, couchesActives, type Cible, type Couche, type Etat } from '../etat';
import type { Modele } from '../modele';
import type { CollectionPoints, ProprietesProducteur, ProprietesRelais } from '../types';
import { LIBELLE_NATURE, nombre } from '../ui/format';
import { infobulle, NATURE_POINT, popupChoix, surtitrePoint, type Choix, type TypePoint } from '../ui/infobulle';
import { imageHachures, imageSymbole, type Symbole } from '../ui/symboles';
import { ENCRE_2 } from '../couleurs';
import {
  couleurEcole, couleurIris, filtreDepartements, GROUPES, IDENTIFIANT, MARQUES, peintureCommunes, SOURCES, ZONES,
  ZONES_FICHE, type NomSource, type ZoneFiche,
} from './couches';
import { empriseDepartements, empriseZone, type Emprise } from './emprise';
import type { Fond } from './fond';

setWorkerUrl(urlWorker);

const VIDE: FeatureCollection = { type: 'FeatureCollection', features: [] };
const SYMBOLES: Symbole[] = ['accueils', 'assos', 'producteurs', 'producteurs_autres', 'relais'];
const POINTS = ['ecoles', 'assos', 'accueils', 'producteurs', 'relais'] as const;
const PORTEE_PX = 12; // un point se choisit sans viser juste
const SUPERPOSES_PX = 5;
const SUPERPOSES_MAX = 8; // au-delà (vue éloignée), on ne prend que le plus proche
// Comme dans style.css : sous cette largeur, la fiche couvre cette part de la carte.
const PETIT_ECRAN = 900;
const PART_FICHE = 0.62;

const position = (f: MapGeoJSONFeature): [number, number] => (f.geometry as Point).coordinates as [number, number];

export interface Lien {
  vers: [number, number];
  famille: 'scolaire' | 'alimentation';
}

/** Où montrer une instance : un point (et ses traits), une zone, ou un ensemble de communes. */
export interface Emplacement {
  xy?: [number, number];
  symbole?: Symbole;
  liens?: Lien[];
  zone?: { source: ZoneFiche; id: string };
  communes?: string[];
}

/** Zones cliquables, de la plus précise à la plus vaste. */
const ZONES_CLIC = ['qpv', 'iris', 'cites', 'communes', 'pat'] as const;

export class Carte {
  readonly gl: CarteGL;
  private prete: Promise<void>;
  private features: Feature<Point, { i: number; v: number }>[];
  private chargees = new Set<NomSource>();
  private bulle = new Popup({ closeButton: false, closeOnClick: false, className: 'bulle', maxWidth: '280px', offset: 12 });
  // Fermée par `cliquer` : sinon le clic qui l'ouvre sur un deuxième point la refermerait.
  private fenetre = new Popup({ closeOnClick: false, className: 'bulle fenetre', maxWidth: '320px', offset: 12 });
  private survolee: { source: string; id: number | string } | null = null;
  private dessinEnCours = false;
  private aRedessiner = false;
  private departements: string | null = null; // derniers départements appliqués aux couches

  constructor(
    conteneur: HTMLElement,
    fond: Fond,
    private modele: Modele,
    private etat: Etat,
    private producteurs: CollectionPoints<ProprietesProducteur>,
    private relais: CollectionPoints<ProprietesRelais>,
    private ouvrir: (c: Cible) => void,
  ) {
    const t = modele.t;
    this.features = t.uai.map((_, i) => ({
      type: 'Feature', id: i, geometry: { type: 'Point', coordinates: [t.lon[i], t.lat[i]] }, properties: { i, v: -1 },
    }));
    const [o, s, e, n] = modele.meta.bbox;
    this.gl = new CarteGL({
      container: conteneur,
      style: fond.style,
      bounds: [[o, s], [e, n]],
      fitBoundsOptions: { padding: 12 },
      maxBounds: [[o - 2, s - 1.5], [e + 2, n + 1.5]],
      minZoom: 7,
      maxZoom: 18.5,
      attributionControl: false,
      dragRotate: false,
      pitchWithRotate: false,
      touchPitch: false,
    });
    this.gl.touchZoomRotate.disableRotation();
    this.gl.keyboard.disableRotation();
    this.gl.addControl(new NavigationControl({ showCompass: false }), 'top-right');
    this.gl.addControl(new ScaleControl({ unit: 'metric' }), 'bottom-right');
    this.gl.addControl(new AttributionControl({
      compact: true,
      customAttribution:
        '<a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">' +
        '© contributeurs OpenStreetMap</a> (ODbL)',
    }), 'bottom-right');
    this.prete = new Promise((resolve) => {
      this.gl.once('style.load', () => {
        this.installer(fond.avant);
        resolve();
      });
    });
    this.ecouter();
  }

  // ---------------------------------------------------------------- mise en place
  private installer(avant: string | undefined): void {
    for (const s of SYMBOLES) this.gl.addImage(`s-${s}`, imageSymbole(s), { pixelRatio: 2 });
    this.gl.addImage('hachures', imageHachures(ENCRE_2), { pixelRatio: 2 });
    for (const s of SOURCES) {
      this.gl.addSource(s, { type: 'geojson', data: VIDE, ...(IDENTIFIANT[s] ? { promoteId: IDENTIFIANT[s] } : {}) });
    }
    for (const c of ZONES) this.gl.addLayer(c, avant);
    for (const c of MARQUES) this.gl.addLayer(c);
    for (const c of COUCHES) this.montrer(c, couchesActives(this.etat)[c]);
    this.filtrerDepartements();
    this.colorer();
    this.dessiner();
  }

  private source(nom: NomSource): GeoJSONSource {
    return this.gl.getSource(nom) as GeoJSONSource;
  }

  private montrer(couche: Couche, visible: boolean): void {
    // Étape 2 : les limites des communes restent, sans couleur ; la couche Communes ajoute la couleur du score.
    const limites = couche === 'communes' && this.etat.etape === 'ecoles';
    if (visible || limites) void this.charger(couche);
    for (const id of GROUPES[couche]) {
      const montre = visible || (limites && id === 'communes-trait');
      this.gl.setLayoutProperty(id, 'visibility', montre ? 'visible' : 'none');
    }
  }

  /** Données d'une couche : lues la première fois qu'elle est affichée. */
  private async charger(couche: Couche): Promise<void> {
    if (couche === 'ecoles' || this.chargees.has(couche)) return;
    this.chargees.add(couche);
    try {
      if (couche === 'producteurs') await this.source('producteurs').setData(this.producteurs);
      else if (couche === 'relais') await this.source('relais').setData(this.relais);
      else if (couche === 'accueils' || couche === 'assos') {
        await this.source(couche).setData(adresse(`points/${couche}.geojson`));
      } else if (couche === 'pat') await this.source('pat').setData(await chargerPats());
      else await this.source(couche).setData(await chargerZone(couche));
    } catch (e) {
      this.chargees.delete(couche);
      console.error(`Couche ${couche} non chargée :`, e);
    }
  }

  // ---------------------------------------------------------------- mises à jour
  async majCouches(): Promise<void> {
    await this.prete;
    for (const c of COUCHES) this.montrer(c, couchesActives(this.etat)[c]);
  }

  /** Départements choisis : chaque couche ne garde que les leurs (les écoles le sont déjà par le classement). */
  async majDepartements(): Promise<void> {
    await this.prete;
    this.filtrerDepartements();
  }

  private filtrerDepartements(): void {
    const deps = this.etat.filtres.departements;
    if (deps.join() === this.departements) return; // les autres filtres ne changent rien aux couches
    this.departements = deps.join();
    for (const c of COUCHES) {
      if (c === 'ecoles') continue;
      for (const id of GROUPES[c]) this.gl.setFilter(id, filtreDepartements(c, deps));
    }
  }

  async majColoration(): Promise<void> {
    await this.prete;
    this.colorer();
    this.dessiner();
  }

  private colorer(): void {
    this.gl.setPaintProperty('ecoles', 'circle-color', couleurEcole(this.etat.coloration));
    this.gl.setPaintProperty('iris', 'fill-color', couleurIris(this.etat.iris));
  }

  /** Score de chaque commune (aligné sur meta.communes) : la couche Communes en prend sa couleur, aux deux étapes. */
  async colorerCommunes(scores: (number | null)[]): Promise<void> {
    await this.prete;
    this.modele.meta.communes.forEach((c, k) => {
      this.gl.setFeatureState({ source: 'communes', id: c.code }, { score: scores[k] ?? -1 });
    });
    const { couleur, opacite } = peintureCommunes();
    this.gl.setPaintProperty('communes', 'fill-color', couleur);
    this.gl.setPaintProperty('communes', 'fill-opacity', opacite);
  }

  async majEcoles(): Promise<void> {
    await this.prete;
    this.dessiner();
  }

  /** Envoie les écoles visibles ; si un envoi est en cours, un seul autre suit (curseurs déplacés vite). */
  private dessiner(): void {
    if (this.dessinEnCours) {
      this.aRedessiner = true;
      return;
    }
    const { modele, etat } = this;
    const c = etat.coloration;
    const features = modele.visibles.map((i) => {
      const f = this.features[i];
      f.properties.v = (c === 'score' ? modele.scores[i] : modele.valeur(c, i)) ?? -1;
      return f;
    });
    this.dessinEnCours = true;
    void this.source('ecoles').setData({ type: 'FeatureCollection', features }).finally(() => {
      this.dessinEnCours = false;
      if (this.aRedessiner) {
        this.aRedessiner = false;
        this.dessiner();
      }
    });
  }

  /** Marque l'instance choisie, même si sa couche est masquée ; un emplacement vide efface la marque. */
  async choisir({ xy, symbole, liens = [], zone, communes = [] }: Emplacement): Promise<void> {
    await this.prete;
    void this.source('selection').setData(xy === undefined ? VIDE : {
      type: 'Feature', geometry: { type: 'Point', coordinates: xy }, properties: symbole ? { symbole } : {},
    });
    const traits: Feature<LineString>[] = xy === undefined ? [] : liens.map((l) => ({
      type: 'Feature', geometry: { type: 'LineString', coordinates: [xy, l.vers] }, properties: { famille: l.famille },
    }));
    void this.source('liens').setData({ type: 'FeatureCollection', features: traits });
    if (zone) void this.charger(zone.source);
    for (const z of Object.keys(ZONES_FICHE) as ZoneFiche[]) {
      const id = zone?.source === z ? zone.id : '';
      for (const c of [`${z}-choisi`, `${z}-choisi-trait`]) this.gl.setFilter(c, ['==', ['get', ZONES_FICHE[z]], id]);
    }
    const choisies = new Set(communes);
    const codes = [...communes, ...this.modele.meta.communes.filter((c) => c.mere && choisies.has(c.mere)).map((c) => c.code)];
    if (codes.length) void this.charger('communes');
    this.gl.setFilter('communes-choisie', ['in', ['get', 'code'], ['literal', codes]]);
  }

  /** Hauteur de carte cachée par la fiche (petits écrans, où elle s'ouvre par-dessus). */
  private cachee(): number {
    return window.innerWidth <= PETIT_ECRAN ? this.gl.getContainer().clientHeight * PART_FICHE : 0;
  }

  allerEcole(i: number): void {
    const t = this.modele.t;
    this.gl.flyTo({
      center: [t.lon[i], t.lat[i]], zoom: Math.max(this.gl.getZoom(), 13.5), offset: [0, -this.cachee() / 2], duration: 900,
    });
  }

  allerCommune(code: string): void {
    const c = this.modele.meta.communes.find((x) => x.code === code);
    if (c) this.cadrer(c.bbox, this.cachee());
  }

  /** Ensemble de communes (retenues à l'étape 1) : cadre qui les contient toutes. */
  allerCommunes(codes: string[]): void {
    const choisies = this.modele.meta.communes.filter((c) => codes.includes(c.code));
    if (!choisies.length) return;
    const e: Emprise = [
      Math.min(...choisies.map((c) => c.bbox[0])), Math.min(...choisies.map((c) => c.bbox[1])),
      Math.max(...choisies.map((c) => c.bbox[2])), Math.max(...choisies.map((c) => c.bbox[3])),
    ];
    this.cadrer(e, this.etat.selection === null ? 0 : this.cachee());
  }

  allerEmplacement({ xy, zone, communes }: Emplacement): void {
    if (xy) this.allerPoint(xy);
    else if (zone) this.allerZone(zone.source, zone.id).catch(console.error);
    else if (communes) this.allerCommunes(communes);
  }

  allerDepartements(deps: readonly string[]): void {
    const e = empriseDepartements(this.modele.meta, deps);
    if (e) this.cadrer(e, this.etat.selection === null ? 0 : this.cachee());
  }

  async allerZone(source: ZoneFiche, id: string): Promise<void> {
    const zone = (await chargerZone(source)).features.find((f) => f.properties?.[ZONES_FICHE[source]] === id);
    const e = zone && empriseZone(zone.geometry);
    if (e) this.cadrer(e, this.cachee());
  }

  private cadrer(emprise: Emprise, cachee: number): void {
    const bord = cachee ? 20 : 48;
    this.gl.fitBounds(emprise, {
      padding: { top: bord, left: bord, right: bord, bottom: bord + cachee }, maxZoom: 14, duration: 900,
    });
  }

  allerPoint(xy: [number, number]): void {
    this.gl.flyTo({ center: xy, zoom: Math.max(this.gl.getZoom(), 14), offset: [0, -this.cachee() / 2], duration: 900 });
  }

  // ---------------------------------------------------------------- souris
  private ecouter(): void {
    this.gl.on('mousemove', (e) => this.survoler(e));
    this.gl.on('mouseout', () => this.quitter());
    this.gl.on('click', (e) => this.cliquer(e));
  }

  private couchesPoints(): string[] {
    return POINTS.filter((c) => couchesActives(this.etat)[c] && this.gl.getLayer(c));
  }

  /** Points à PORTEE_PX près du pointeur, du plus proche au plus loin ; à distance égale, les écoles d'abord. */
  private pointsSous(e: MapMouseEvent): MapGeoJSONFeature[] {
    const { x, y } = e.point;
    const layers = this.couchesPoints();
    if (!layers.length) return [];
    const vus = new Set<string>();
    const trouves: { f: MapGeoJSONFeature; d: number }[] = [];
    for (const f of this.gl.queryRenderedFeatures(
      [[x - PORTEE_PX, y - PORTEE_PX], [x + PORTEE_PX, y + PORTEE_PX]], { layers },
    )) {
      const cle = `${f.layer.id} ${String(f.properties.i ?? f.properties.id)}`;
      if (vus.has(cle)) continue; // un point au bord de deux tuiles est rendu deux fois
      vus.add(cle);
      const d = this.ecart(f, e.point) + (f.layer.id === 'ecoles' ? 0 : 0.5);
      if (d <= PORTEE_PX + 4) trouves.push({ f, d });
    }
    return trouves.sort((a, b) => a.d - b.d).map((t) => t.f);
  }

  private ecart(f: MapGeoJSONFeature, q: { x: number; y: number }): number {
    const p = this.gl.project(position(f));
    return Math.hypot(p.x - q.x, p.y - q.y);
  }

  /** Points superposés au premier (même adresse, ou trop proches pour être distingués à ce zoom). */
  private superposes(points: MapGeoJSONFeature[]): MapGeoJSONFeature[] {
    if (!points.length) return [];
    const p = this.gl.project(position(points[0]));
    const l = points.filter((f) => this.ecart(f, p) <= SUPERPOSES_PX);
    return l.length <= SUPERPOSES_MAX ? l : [points[0]];
  }

  /** Zones affichées sous le pointeur, une seule fois chacune, de la plus précise à la plus vaste. */
  private zonesSous(e: MapMouseEvent): MapGeoJSONFeature[] {
    const layers = ZONES_CLIC.filter((z) => couchesActives(this.etat)[z] && this.gl.getLayer(z));
    if (!layers.length) return [];
    const vues = new Map<string, MapGeoJSONFeature>();
    for (const f of this.gl.queryRenderedFeatures(e.point, { layers })) {
      vues.set(`${f.layer.id} ${String(f.properties.id ?? f.properties.iris ?? f.properties.code)}`, f);
    }
    const rang = (f: MapGeoJSONFeature): number => ZONES_CLIC.indexOf(f.layer.id as (typeof ZONES_CLIC)[number]);
    return [...vues.values()].sort((a, b) => rang(a) - rang(b));
  }

  /** Zone dont le nom, écrit sur la carte, est sous le pointeur : elle s'ouvre sans passer par la liste. */
  private nomSous(e: MapMouseEvent): MapGeoJSONFeature | null {
    const layers = (['pat', 'cites', 'qpv'] as const).filter((z) => couchesActives(this.etat)[z]).map((z) => `${z}-nom`);
    return (layers.length && this.gl.queryRenderedFeatures(e.point, { layers })[0]) || null;
  }

  private cibleZone(f: MapGeoJSONFeature): Cible {
    const p = f.properties;
    switch (f.source) {
      case 'communes': return { type: 'commune', code: String(p.code) };
      case 'pat': return { type: 'pat', id: String(p.id) };
      case 'iris': return { type: 'acteur', nature: 'iris', id: String(p.iris) };
      default: return { type: 'acteur', nature: 'dispositif', id: String(p.id) };
    }
  }

  private ciblePoint(f: MapGeoJSONFeature): Cible {
    return f.layer.id === 'ecoles' ? { type: 'ecole', uai: this.modele.t.uai[f.properties.i as number] }
      : { type: 'acteur', nature: NATURE_POINT[f.layer.id as TypePoint], id: String(f.properties.id) };
  }

  private choixPoint(f: MapGeoJSONFeature): Choix {
    const ouvrir = (): void => this.choisirDans(this.ciblePoint(f));
    if (f.layer.id !== 'ecoles') {
      return { surtitre: surtitrePoint(f.layer.id as TypePoint, f.properties), nom: String(f.properties.nom), ouvrir };
    }
    const i = f.properties.i as number;
    const s = this.modele.scores[i];
    return { surtitre: LIBELLE_NATURE.ecole[0], nom: this.modele.t.nom[i], valeur: s === null ? '–' : nombre(s), ouvrir };
  }

  private choixZone(f: MapGeoJSONFeature): Choix {
    const surtitre: Record<string, string> = {
      communes: 'Commune', pat: LIBELLE_NATURE.pat[0], iris: LIBELLE_NATURE.iris[0], qpv: 'Quartier prioritaire',
      cites: 'Cité éducative',
    };
    return {
      surtitre: surtitre[f.source], nom: String(f.properties.nom), ouvrir: () => this.choisirDans(this.cibleZone(f)),
    };
  }

  private choisirDans(c: Cible): void {
    this.fenetre.remove();
    this.ouvrir(c);
  }

  private marquer(source: string | null, id?: number | string): void {
    if (this.survolee) {
      if (this.survolee.source === source && this.survolee.id === id) return;
      this.gl.setFeatureState(this.survolee, { survol: false });
      this.survolee = null;
    }
    if (source !== null && id !== undefined) {
      this.survolee = { source, id };
      this.gl.setFeatureState(this.survolee, { survol: true });
    }
  }

  private survoler(e: MapMouseEvent): void {
    const groupe = this.superposes(this.pointsSous(e));
    const curseur = this.gl.getCanvas().style;
    if (groupe.length) {
      const [f] = groupe;
      curseur.cursor = 'pointer';
      this.marquer(f.layer.id === 'ecoles' ? 'ecoles' : null, f.id);
      this.bulle
        .setLngLat(position(f))
        .setDOMContent(infobulle(f.layer.id as TypePoint | 'ecoles', f.properties, this.modele, groupe.length - 1))
        .addTo(this.gl);
      return;
    }
    this.bulle.remove();
    const zones = this.zonesSous(e);
    const commune = zones.find((f) => f.source === 'communes');
    curseur.cursor = zones.length || this.nomSous(e) ? 'pointer' : '';
    this.marquer(commune ? 'communes' : null, commune?.id);
  }

  private quitter(): void {
    this.bulle.remove();
    this.marquer(null);
  }

  private cliquer(e: MapMouseEvent): void {
    const groupe = this.superposes(this.pointsSous(e));
    this.bulle.remove();
    this.fenetre.remove();
    if (groupe.length > 1) {
      this.proposer(position(groupe[0]), `${groupe.length} points au même endroit`, groupe.map((f) => this.choixPoint(f)));
      return;
    }
    if (groupe.length === 1) {
      this.ouvrir(this.ciblePoint(groupe[0]));
      return;
    }
    const nom = this.nomSous(e);
    const zones = nom ? [nom] : this.zonesSous(e);
    if (zones.length === 1) this.ouvrir(this.cibleZone(zones[0]));
    else if (zones.length) this.proposer(e.lngLat.toArray(), 'À cet endroit', zones.map((f) => this.choixZone(f)));
  }

  private proposer(xy: [number, number], titre: string, choix: Choix[]): void {
    this.fenetre.setLngLat(xy).setDOMContent(popupChoix(titre, choix)).addTo(this.gl);
  }
}
