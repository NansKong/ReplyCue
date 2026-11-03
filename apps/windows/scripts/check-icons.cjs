const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { resolve, basename } = require('node:path');
const { NtExecutable, NtExecutableResource, Resource, Data } = require('resedit');

const root = resolve(__dirname, '../../..');
const version = require('../package.json').version;
const expected = Data.IconFile.from(readFileSync(resolve(__dirname, '../electron/icon.ico'))).icons;
const files = [
  resolve(root, 'releases/windows/win-unpacked/ReplyCue.exe'),
  resolve(root, 'releases/windows/win-unpacked/resources/engine/CopilotEngine.exe'),
  resolve(root, `releases/windows/ReplyCue-Setup-${version}.exe`),
];
for (const file of files) {
  const pe = NtExecutable.from(readFileSync(file));
  const resources = NtExecutableResource.from(pe);
  const groups = Resource.IconGroupEntry.fromEntries(resources.entries);
  assert.ok(groups.length, `No icon resources in ${file}`);
  const icons = groups[0].getIconItemsFromEntries(resources.entries);
  assert.equal(icons.length, expected.length, `${file}: wrong number of icon sizes`);
  for (const { data } of expected) {
    // ICO/group headers encode a 256px dimension as zero.
    assert.ok(icons.some(icon => (icon.width || 256) === data.width && (icon.height || 256) === data.height
      && Buffer.from(icon.bin).equals(Buffer.from(data.bin))), `${file}: favicon mismatch at ${data.width}px`);
  }
  console.log(JSON.stringify({ check: 'embedded-icon', file: basename(file), passed: true, sizes: icons.map(icon => icon.width || 256) }));
}
