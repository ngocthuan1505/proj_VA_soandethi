import {createRequire} from 'node:module';
import {existsSync} from 'node:fs';
import path from 'node:path';
import os from 'node:os';
export const bundledRoot=path.join(os.homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules');
const local=createRequire(import.meta.url);
export function dependency(name){try{return local(name);}catch(e){if(!existsSync(bundledRoot))throw e;return createRequire(path.join(bundledRoot,'_runtime.cjs'))(name);}}
export function dependencyPath(name){try{return local.resolve(name);}catch(e){return createRequire(path.join(bundledRoot,'_runtime.cjs')).resolve(name);}}
export function chromePath(){const candidates=[process.env.BROWSER_PATH,'C:/Program Files/Google/Chrome/Application/chrome.exe','C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'];return candidates.find(p=>p&&existsSync(p));}
