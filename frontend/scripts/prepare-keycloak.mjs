import { copyFile, mkdir, readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const theme = path.join(root, 'keycloak-theme/copper/login/resources/fonts');
await mkdir(theme, { recursive: true });
for (const subset of ['latin', 'cyrillic']) {
  await copyFile(path.join(root, `node_modules/@fontsource-variable/golos-text/files/golos-text-${subset}-wght-normal.woff2`), path.join(theme, `golos-text-${subset}.woff2`));
}
await copyFile(path.join(root, 'node_modules/@fontsource-variable/golos-text/LICENSE'), path.join(theme, 'LICENSE.txt'));
const realm = JSON.parse(await readFile(path.resolve(root, '../infra/keycloak/realm.json'), 'utf8'));
Object.assign(realm, { loginTheme: 'copper', internationalizationEnabled: true, supportedLocales: ['ru', 'en'], defaultLocale: 'ru' });
await mkdir(path.join(root, 'infra'), { recursive: true });
await writeFile(path.join(root, 'infra/realm.json'), JSON.stringify(realm, null, 2) + '\n');
