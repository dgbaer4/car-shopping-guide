import {
  decodeObservations, encodeObservations, observationGroups, observationTypes,
  priceScopes, provenance, sharedObservation, validateObservation,
} from './observations.mjs';
import { intakeUrl } from './observation-config.mjs';

const prefix = 'csg-observation-v1/';
const money = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' });
const fields = [
  ['year', 'Model year', { type: 'number', min: 1886, max: new Date().getUTCFullYear() + 2 }],
  ['make', 'Manufacturer', { maxlength: 70 }],
  ['model', 'Model', { maxlength: 90 }],
  ['condition', 'Condition', { options: { new: 'New', used: 'Used' } }],
  ['price', 'Observed price (USD)', { type: 'number', min: '0.01', max: 10000000, step: '0.01', inputmode: 'decimal' }],
  ['type', 'Price observation type', { options: observationTypes }],
  ['scope', 'Price scope', { options: priceScopes }],
  ['trim', 'Trim', { maxlength: 90 }],
  ['mileage', 'Mileage', { type: 'number', min: 0, max: 2000000 }],
  ['powertrain', 'Powertrain', { maxlength: 60 }],
  ['drivetrain', 'Drivetrain', { maxlength: 40 }],
  ['zip', 'Vehicle ZIP code', { maxlength: 5, inputmode: 'numeric', pattern: '[0-9]{5}' }],
  ['sellerType', 'Seller type', { options: { dealer: 'Dealer', private: 'Private seller', other: 'Other' } }],
  ['listingUrl', 'Original listing URL (HTTPS)', { type: 'url', maxlength: 500 }],
  ['vehicleNotes', 'Vehicle details you may choose to share', { maxlength: 500 }],
  ['nickname', 'Contributor nickname (optional, unverified)', { maxlength: 40 }],
];

function append(parent, tag, text = '') {
  const node = document.createElement(tag);
  node.textContent = text;
  parent.append(node);
  return node;
}

function button(parent, text, action) {
  const node = append(parent, 'button', text);
  node.type = 'button';
  node.addEventListener('click', action);
  return node;
}

function select(parent, options, current) {
  const node = append(parent, 'select');
  append(node, 'option', 'Select…').value = '';
  for (const [value, label] of Object.entries(options)) append(node, 'option', label).value = value;
  node.value = current ?? '';
  return node;
}

function readRecords() {
  return Object.keys(localStorage).filter(key => key.startsWith(prefix)).map(key =>
    validateObservation(JSON.parse(localStorage.getItem(key))));
}

export function observationLink(parent, item, currentCondition) {
  button(parent, 'Add Vehicle Observation', () => document.dispatchEvent(new CustomEvent('csg:add-observation', {
    detail: {
      year: item.year, make: item.make, model: item.model, powertrain: item.power,
      drivetrain: item.vehicle.drivetrain, condition: currentCondition(), catalogId: item.id,
    },
  })));
  const link = append(parent, 'a', 'View related observations');
  link.href = '#observations-for-' + encodeURIComponent(item.id);
}

export function initObservations({ showRecommendation }) {
  const panel = document.getElementById('shopping-tracker');
  const status = document.getElementById('observation-status');
  const content = document.getElementById('observation-content');
  let revealRejected = false;
  let filter;
  let lastFocus;

  function openPanel() {
    if (panel.hidden) lastFocus = document.activeElement;
    panel.hidden = false;
    status.textContent = '';
  }

  function focusPanel(node = panel.querySelector('h2')) {
    node.tabIndex = -1;
    node.focus();
    node.scrollIntoView({ block: 'nearest' });
  }

  function safely(action) {
    try {
      action();
    } catch (error) {
      status.textContent = error.name === 'QuotaExceededError' || error.name === 'SecurityError'
        ? 'Browser storage is unavailable or full. Keep this page open and check your browser settings.'
        : error.message;
    }
  }

  function download(file, extension, contents) {
    const url = URL.createObjectURL(new Blob([contents], { type: extension === 'md' ? 'text/markdown' : 'application/json' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = file + '.' + extension;
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
  }

  function exportActions(parent, records, options = {}) {
    for (const [ext, label] of [['json', 'JSON'], ['md', 'Markdown']]) {
      button(parent, label, () => safely(() => download(
        options.shared ? 'csg-share' : 'csg-private-backup', ext,
        encodeObservations(records, { markdown: ext === 'md', ...options }),
      )));
    }
  }

  function editor(seed = {}, existing = false) {
    openPanel();
    content.replaceChildren();
    const heading = append(content, 'h3', existing ? 'Edit vehicle observation' : 'Add vehicle observation');
    const form = append(content, 'form');
    const grid = append(form, 'div');
    grid.className = 'observation-grid';
    const optional = append(form, 'details');
    append(optional, 'summary', 'Optional vehicle details');
    const optionalGrid = append(optional, 'div');
    optionalGrid.className = 'observation-grid';
    optional.addEventListener('invalid', () => { optional.open = true; }, true);

    for (const [index, [key, caption, { options, ...attributes }]] of fields.entries()) {
      const required = index < 7;
      const label = append(required ? grid : optionalGrid, 'label', caption);
      const value = key === 'price' ? seed.priceCents == null ? '' : seed.priceCents / 100 : seed[key];
      const node = options ? select(label, options, value) : append(label, 'input');
      for (const [name, setting] of Object.entries(attributes)) node.setAttribute(name, setting);
      if (!options) node.value = value ?? '';
      node.name = key;
      node.required = required && !(existing && key === 'price' && seed.priceCents === null);
    }
    const notes = append(append(form, 'label', 'Private shopping notes'), 'textarea');
    notes.name = 'privateNotes';
    notes.maxLength = 2000;
    notes.value = seed.privateNotes ?? '';
    append(form, 'p', 'Saving keeps this observation and your notes in this browser.');
    append(form, 'button', 'Save observation').className = 'primary';
    button(form, 'Cancel', () => tracker());
    form.addEventListener('submit', event => {
      event.preventDefault();
      safely(() => {
        const values = Object.fromEntries([...new FormData(form)].map(([key, value]) =>
          [key, key === 'privateNotes' ? value : value.trim()]).filter(([, value]) => value !== ''));
        const { year, price, mileage, ...textValues } = values;
        const sameIdentity = Number(year) === seed.year && ['make', 'model', 'powertrain', 'drivetrain']
          .every(key => (textValues[key] ?? '') === (seed[key] ?? ''));
        const record = validateObservation({
          ...textValues, schemaVersion: 1, id: seed.id ?? crypto.randomUUID(),
          observedAt: seed.observedAt ?? new Date().toISOString(), year: Number(year),
          priceCents: price === undefined ? null : Math.round(Number(price) * 100),
          ...(mileage === undefined ? {} : { mileage: Number(mileage) }),
          ...(sameIdentity && seed.catalogId ? { catalogId: seed.catalogId } : {}),
          source: 'contributed', verification: 'unverified', interest: seed.interest ?? 'POSSIBLE',
        });
        if (existing && localStorage.getItem(prefix + seed.id) !== JSON.stringify(seed)) {
          throw Error('This observation changed in another tab. Reopen it before editing.');
        }
        localStorage.setItem(prefix + record.id, JSON.stringify(record));
        tracker(record.id);
        status.textContent = 'Saved locally.';
      });
    });
    focusPanel(heading);
  }

  function contribution(record) {
    openPanel();
    content.replaceChildren();
    const heading = append(content, 'h3', 'Share an observation');
    append(content, 'p', 'Sharing is optional. The project owner receives the selected vehicle data in a private spreadsheet and may review sanitized pricing for future use. Keep names, contact information, VINs and other identifiers out of fields you share.');
    const extraLabel = append(content, 'label', ' Include ZIP, listing URL path, vehicle details and unverified nickname if entered');
    const extra = document.createElement('input');
    extra.type = 'checkbox';
    extraLabel.prepend(extra);
    const preview = append(content, 'pre');
    const consentLabel = append(content, 'label', ' I agree to share the data shown above with the project owner for pricing review.');
    const consent = document.createElement('input');
    consent.type = 'checkbox';
    consentLabel.prepend(consent);
    const actions = append(content, 'div');
    actions.className = 'observation-actions';
    const copy = button(actions, 'Copy contribution JSON', async () => {
      try {
        await navigator.clipboard.writeText(preview.textContent);
        status.textContent = 'Copied. Submit the same JSON on the intake page to get a receipt.';
      } catch {
        status.textContent = 'Clipboard unavailable. Select and copy the preview, or download JSON.';
      }
    });
    const downloads = append(actions, 'span');
    if (/^https:\/\/script\.google\.com\/macros\/s\/[\w-]+\/exec$/.test(intakeUrl)) {
      const link = append(actions, 'a', 'Open secure intake');
      link.href = intakeUrl;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
    } else {
      append(content, 'p', 'Hosted intake is unavailable in this build. You can download a contribution for owner-mediated review.');
    }
    append(content, 'p', 'Delivery is confirmed on the intake page only. If the result is unclear, retry with the same JSON and observation ID.');
    button(content, 'Back to tracker', () => tracker(record.id));
    function update() {
      const shared = sharedObservation(record, extra.checked);
      preview.textContent = encodeObservations([shared], { shared: true });
      downloads.replaceChildren();
      exportActions(downloads, [shared], { shared: true });
      actions.hidden = !consent.checked;
    }
    extra.onchange = () => { consent.checked = false; update(); };
    consent.onchange = update;
    update();
    focusPanel(heading);
  }

  function tracker(targetId, keepFocus = false) {
    openPanel();
    content.replaceChildren();
    const actions = append(content, 'div');
    actions.className = 'observation-actions';
    button(actions, 'Add Vehicle Observation', () => { filter = undefined; editor(); });
    if (filter) button(actions, 'Show all observations', () => { filter = undefined; tracker(); });
    append(content, 'p', 'Observations and interest choices stay on this device. Clearing browser data or using private browsing can remove them. Save a private backup to transfer or recover them.');
    let records = [];
    safely(() => { records = readRecords(); });
    if (filter) records = records.filter(record => record.catalogId === filter);

    const backup = append(content, 'details');
    append(backup, 'summary', 'Export or import observations');
    append(backup, 'p', 'Private backups include shopping notes and interest selections.');
    exportActions(backup, records);
    const importLabel = append(backup, 'label', 'Restore private backup (JSON or Markdown)');
    const importer = append(importLabel, 'input');
    importer.type = 'file';
    importer.accept = '.json,.md';
    importer.onchange = async () => {
      try {
        const file = importer.files[0];
        if (!file || file.size > 16000000) throw Error('Choose a backup up to 16 MB.');
        const incoming = decodeObservations(await file.text());
        let imported = 0;
        try {
          for (const record of incoming) {
            if (localStorage.getItem(prefix + record.id) !== null) continue;
            localStorage.setItem(prefix + record.id, JSON.stringify(record));
            imported += 1;
          }
        } catch {
          tracker();
          status.textContent = `Restored ${imported} before browser storage became unavailable. Retry with the same backup to resume.`;
          return;
        }
        tracker();
        status.textContent = `Restored ${imported}. Skipped ${incoming.length - imported} existing IDs.`;
      } catch (error) {
        status.textContent = error.message;
      }
    };
    if (!records.length) append(content, 'p', 'No observations match this view.');
    for (const [interest, group] of observationGroups(records)) {
      if (!group.length || (interest === 'DON’T THINK SO' && !revealRejected && !group.some(record => record.id === targetId))) continue;
      const section = append(content, 'section');
      append(section, 'h3', interest);
      for (const record of group) {
        const card = append(section, 'article');
        card.id = 'observation-' + record.id;
        append(card, 'h4', `${record.year} ${record.make} ${record.model}`);
        append(card, 'p', [
          record.condition === 'new' ? 'New' : 'Used', record.trim,
          record.priceCents == null ? 'Price unavailable' : money.format(record.priceCents / 100),
          priceScopes[record.scope],
        ].filter(Boolean).join(' · '));
        append(card, 'p', `${provenance.contributed} · ${provenance[record.type] ?? observationTypes[record.type]} · Unverified · ${record.observedAt.slice(0, 10)}`);
        if (record.privateNotes) append(card, 'p', record.privateNotes).className = 'observation-notes';
        const label = append(card, 'label', 'Interest');
        const choice = select(label, { GOOD: 'GOOD', POSSIBLE: 'POSSIBLE', 'DON’T THINK SO': 'DON’T THINK SO' }, record.interest);
        choice.firstChild.remove();
        choice.onchange = () => {
          safely(() => {
            if (localStorage.getItem(prefix + record.id) !== JSON.stringify(record)) {
              throw Error('This observation changed in another tab. Reopen the tracker before editing.');
            }
            const updated = { ...record, interest: choice.value };
            localStorage.setItem(prefix + record.id, JSON.stringify(updated));
            const rejected = updated.interest === 'DON’T THINK SO' && !revealRejected;
            tracker(rejected ? undefined : record.id);
            status.textContent = rejected ? 'Moved to DON’T THINK SO. Use the control below to see it.' : 'Interest saved.';
          });
          choice.value = record.interest;
        };
        const links = append(card, 'div');
        links.className = 'observation-actions';
        if (record.catalogId) {
          const link = append(links, 'a', 'Recommendation and ownership costs');
          link.href = '#vehicle-' + encodeURIComponent(record.catalogId);
          link.onclick = event => {
            event.preventDefault();
            showRecommendation(record.catalogId);
          };
        }
        if (record.listingUrl) {
          const link = append(links, 'a', 'Original listing');
          link.href = record.listingUrl;
          link.rel = 'noopener noreferrer';
          link.target = '_blank';
        }
        append(links, 'a', 'Observation permalink').href = '#' + card.id;
        button(links, 'Edit', () => editor(record, true));
        if (record.priceCents != null) button(links, 'Share or export contribution', () => contribution(record));
        button(links, 'Delete', () => {
          if (!confirm('Delete this observation from this browser?')) return;
          safely(() => {
            if (localStorage.getItem(prefix + record.id) !== JSON.stringify(record)) {
              throw Error('This observation changed in another tab. Reopen the tracker before deleting.');
            }
            localStorage.removeItem(prefix + record.id);
            tracker();
            status.textContent = 'Deleted locally.';
          });
        });
        const individual = append(card, 'details');
        append(individual, 'summary', 'Export private copy');
        exportActions(individual, [record]);
      }
    }
    const rejected = records.filter(record => record.interest === 'DON’T THINK SO');
    if (rejected.length) {
      const visible = revealRejected || rejected.some(record => record.id === targetId);
      const toggle = button(content, `${visible ? 'Hide' : 'Show'} DON’T THINK SO (${rejected.length})`, () => {
        revealRejected = !visible;
        tracker(undefined, true);
        content.lastElementChild.focus();
      });
      toggle.setAttribute('aria-expanded', String(visible));
    }
    if (!keepFocus) focusPanel((targetId && document.getElementById('observation-' + targetId)) || undefined);
  }

  function close() {
    panel.hidden = true;
    if (/^#observation(?:s-for)?-/.test(location.hash)) history.replaceState(null, '', location.pathname + location.search);
    if (lastFocus?.isConnected) lastFocus.focus();
  }

  function followHash() {
    if (location.hash.startsWith('#observations-for-')) {
      safely(() => { filter = decodeURIComponent(location.hash.slice(18)); tracker(); });
    } else if (/^#observation-[0-9a-f-]{36}$/.test(location.hash)) {
      filter = undefined;
      tracker(location.hash.slice(13));
    }
  }
  document.getElementById('open-shopping-tracker').onclick = () => { filter = undefined; tracker(); };
  document.getElementById('close-shopping-tracker').onclick = close;
  document.addEventListener('csg:add-observation', event => {
    filter = event.detail.catalogId;
    editor(event.detail);
  });
  window.addEventListener('hashchange', followHash);
  followHash();
  return close;
}
