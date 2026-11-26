import { readFileSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

export function intakeValidator() {
  const module = readFileSync(new URL('../engine/observations.mjs', import.meta.url), 'utf8');
  // Apps Script does not support ES modules and hides RPCs ending in "_".
  return '// Generated from engine/observations.mjs.\n' + module
    .replace(/^export /gm, '')
    .replace(/\b(check|textValue|listingUrl|validateObservation|sharedObservation|observationGroups|encodeObservations|decodeObservations)(?=\()/g, '$1_');
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const output = process.argv[2];
  if (!output) throw Error('Provide the output path for ObservationValidation.gs.');
  writeFileSync(output, intakeValidator());
}
