/** Carte MapLibre : fond IGN, couches, survol, clic, sélection. */

import 'maplibre-gl/dist/maplibre-gl.css';

import type { Feature, FeatureCollection, LineString, Point } from 'geojson';
import {
  AttributionControl, GeoJSONSource, Map as CarteGL, NavigationControl, Popup, ScaleControl, setWorkerUrl,
  type MapGeoJSONFeature, type MapMouseEvent,
} from 'maplibre-gl';
import urlWorker from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';

import { adresse, chargerPats, chargerZone } from '../donnees';
import { COUCHES, type Couche, type Etat } from '../etat';
import type { Modele } from '../modele';
import type { CollectionPoints, ProprietesProducteur, ProprietesRelais } from '../types';
import { infobulle, popupGroupe, popupPoint, type TypePoint } from '../ui/infobulle';
import { imageHachures, imageSymbole, type Symbole } from '../ui/symboles';
import { ENCRE_2 } from '../couleurs';
import {
  couleurEcole, couleurIris, GROUPES, IDENTIFIANT, MARQUES, peintureCommunes, SOURCES, ZONES, type NomSource,
} from './couches';
import { empriseDepartement, empriseZone, type Emprise } from './emprise';
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

interface Rappels {
  ecole: (i: number) => void;
  commune: (code: string) => void;
  pat: (id: string) => void;
}

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

  constructor(
    conteneur: HTMLElement,
    fond: Fond,
    private modele: Modele,
    private etat: Etat,
    private producteurs: CollectionPoints<ProprietesProducteur>,
    private relais: CollectionPoints<ProprietesRelais>,
    private rappels: Rappels,
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
    for (const c of COUCHES) this.montrer(c, this.etat.couches[c]);
    this.colorer();
    this.dessiner();
  }

  private source(nom: NomSource): GeoJSONSource {
    return this.gl.getSource(nom) as GeoJSONSource;
  }

  private montrer(couche: Couche, visible: boolean): void {
    if (visible) void this.charger(couche);
    for (const id of GROUPES[couche]) {
      this.gl.setLayoutProperty(id, 'visibility', visible ? 'visible' : 'none');
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
    for (const c of COUCHES) this.montrer(c, this.etat.couches[c]);
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

  /** Étape 1 : score de chaque commune (aligné sur meta.communes) ; étape 2 : communes retenues. */
  async colorerCommunes(scores: (number | null)[], retenues: string[]): Promise<void> {
    await this.prete;
    const gardees = new Set(retenues);
    this.modele.meta.communes.forEach((c, k) => {
      this.gl.setFeatureState(
        { source: 'communes', id: c.code },
        { score: scores[k] ?? -1, retenue: gardees.has(c.code) || (c.mere !== undefined && gardees.has(c.mere)) },
      );
    });
    const { couleur, opacite } = peintureCommunes(this.etat.etape);
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

  async choisirEcole(i: number | null, liens: Lien[] = []): Promise<void> {
    await this.prete;
    const t = this.modele.t;
    const depart = i === null ? null : ([t.lon[i], t.lat[i]] as [number, number]);
    void this.source('selection').setData(depart === null ? VIDE : {
      type: 'Feature', geometry: { type: 'Point', coordinates: depart }, properties: {},
    });
    const traits: Feature<LineString>[] = depart === null ? [] : liens.map((l) => ({
      type: 'Feature', geometry: { type: 'LineString', coordinates: [depart, l.vers] }, properties: { famille: l.famille },
    }));
    void this.source('liens').setData({ type: 'FeatureCollection', features: traits });
  }

  async choisirCommune(code: string | null): Promise<void> {
    await this.prete;
    const codes = code === null ? [] : [code, ...this.modele.meta.communes.filter((c) => c.mere === code).map((c) => c.code)];
    if (codes.length) void this.charger('communes');
    this.gl.setFilter('communes-choisie', ['in', ['get', 'code'], ['literal', codes]]);
  }

  /** Périmètre du PAT choisi, montré même si la couche des PAT est masquée. */
  async choisirPat(id: string | null): Promise<void> {
    await this.prete;
    if (id !== null) void this.charger('pat');
    for (const c of ['pat-choisi', 'pat-choisi-trait']) this.gl.setFilter(c, ['==', ['get', 'id'], id ?? '']);
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

  allerDepartement(dep: string): void {
    const e = empriseDepartement(this.modele.meta, dep);
    if (e) this.cadrer(e, this.etat.selection === null ? 0 : this.cachee());
  }

  async allerPat(id: string): Promise<void> {
    const zone = (await chargerPats()).features.find((f) => f.properties.id === id);
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
    this.gl.flyTo({ center: xy, zoom: Math.max(this.gl.getZoom(), 14), duration: 900 });
  }

  // ---------------------------------------------------------------- souris
  private ecouter(): void {
    this.gl.on('mousemove', (e) => this.survoler(e));
    this.gl.on('mouseout', () => this.quitter());
    this.gl.on('click', (e) => this.cliquer(e));
  }

  private couchesPoints(): string[] {
    return POINTS.filter((c) => this.etat.couches[c] && this.gl.getLayer(c));
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

  private communeSous(e: MapMouseEvent): MapGeoJSONFeature | null {
    if (!this.etat.couches.communes || !this.gl.getLayer('communes')) return null;
    return this.gl.queryRenderedFeatures(e.point, { layers: ['communes'] })[0] ?? null;
  }

  /** PAT dont le nom, affiché sur la carte, est sous le pointeur. */
  private patSous(e: MapMouseEvent): string | null {
    if (!this.etat.couches.pat || !this.gl.getLayer('pat-nom')) return null;
    const f = this.gl.queryRenderedFeatures(e.point, { layers: ['pat-nom'] })[0];
    return f ? String(f.properties.id) : null;
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
    if (this.patSous(e) !== null) {
      curseur.cursor = 'pointer';
      this.marquer(null);
      return;
    }
    const commune = this.communeSous(e);
    curseur.cursor = commune ? 'pointer' : '';
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
    if (!groupe.length) {
      const pat = this.patSous(e);
      if (pat !== null) {
        this.rappels.pat(pat);
        return;
      }
      const commune = this.communeSous(e);
      if (commune) this.rappels.commune(commune.properties.code as string);
      return;
    }
    const [f] = groupe;
    if (groupe.length === 1 && f.layer.id === 'ecoles') {
      this.rappels.ecole(f.properties.i as number);
      return;
    }
    const contenu = groupe.length === 1
      ? popupPoint(f.layer.id as TypePoint, f.properties, this.modele.meta)
      : popupGroupe(
        groupe.map((x) => ({ type: x.layer.id as TypePoint | 'ecoles', p: x.properties })), this.modele,
        (i) => {
          this.fenetre.remove();
          this.rappels.ecole(i);
        },
      );
    this.fenetre.setLngLat(position(f)).setDOMContent(contenu).addTo(this.gl);
  }
}
