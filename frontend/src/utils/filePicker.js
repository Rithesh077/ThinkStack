/**
 * Ask the user for a file on their own disk, and get back a real PATH.
 *
 * This has to be a native dialog. The UI is served over http://127.0.0.1:8000,
 * so a plain `<input type="file">` hands back a File object with no filesystem
 * path -- the browser deliberately withholds it. Registering a model needs the
 * path, because the whole point is to REFERENCE weights where they already sit
 * rather than copy several gigabytes; going through an upload would mean
 * pushing a 7 GB file through the backend to land it somewhere we then have to
 * store twice.
 *
 * Outside the desktop shell (./scripts/dev.sh in a browser) there is no dialog
 * to open, so `pickModelFile` reports that and the caller falls back to a typed
 * path. That fallback is not dead weight: it is also the escape hatch for a
 * user whose file lives somewhere a dialog makes awkward to reach.
 */

/** true only inside the tauri desktop webview. */
export function inTauri() {
  return typeof window !== 'undefined' &&
    (Boolean(window.__TAURI_INTERNALS__) || Boolean(window.__TAURI__));
}

/**
 * Open a native file dialog filtered to gguf weights.
 *
 * @returns {Promise<{path: string|null, reason: string}>}
 *   `path` is null when the user cancelled or no dialog is available; `reason`
 *   distinguishes those, because "you cancelled" needs no message and "there is
 *   no picker here" needs to reveal the manual input.
 */
export async function pickModelFile() {
  if (!inTauri()) return { path: null, reason: 'unsupported' };

  try {
    const { open } = await import('@tauri-apps/plugin-dialog');
    const selected = await open({
      multiple: false,
      directory: false,
      title: 'Choose a GGUF model',
      filters: [{ name: 'GGUF model', extensions: ['gguf'] }],
    });

    // v2 returns a string path, or null on cancel. Older shapes returned an
    // object with `.path`; tolerate both so a plugin bump cannot break import.
    if (!selected) return { path: null, reason: 'cancelled' };
    const path = typeof selected === 'string' ? selected : selected.path;
    return path ? { path, reason: 'ok' } : { path: null, reason: 'cancelled' };
  } catch (err) {
    // A denied capability lands here. Falling back to the typed path keeps
    // import working rather than presenting a button that silently does
    // nothing -- the failure mode the updater button already taught us about.
    console.warn('[filePicker] native dialog unavailable:', err);
    return { path: null, reason: 'unsupported' };
  }
}


/**
 * Ask for a file to LINK into a paper project.
 *
 * Same mechanism as `pickModelFile` and for the same reason: linking records
 * where a file IS, so it needs a path, and a browser file input deliberately
 * withholds one. The filters mirror the suffixes the backend will accept, so a
 * user is not offered a choice that is then refused -- but the backend checks
 * anyway, because a dialog filter is a convenience and not a boundary.
 */
export async function pickProjectFile({ directory = false } = {}) {
  if (!inTauri()) return { path: null, reason: 'unsupported' };

  try {
    const { open } = await import('@tauri-apps/plugin-dialog');
    const selected = await open({
      multiple: false,
      directory,
      title: directory
        ? 'Link a folder into this paper'
        : 'Link a file into this paper',
      // A folder chooser must not be filtered by file extension, or the
      // dialog shows nothing selectable.
      ...(directory ? {} : {
        filters: [
          { name: 'Anything a paper can use',
            extensions: ['tex', 'bib', 'cls', 'sty', 'bst',
                         'png', 'jpg', 'jpeg', 'pdf', 'eps', 'svg',
                         'csv', 'dat', 'txt'] },
        ],
      }),
    });
    if (!selected) return { path: null, reason: 'cancelled' };
    const path = typeof selected === 'string' ? selected : selected.path;
    return path ? { path, reason: 'ok' } : { path: null, reason: 'cancelled' };
  } catch (err) {
    console.warn('[filePicker] native dialog unavailable:', err);
    return { path: null, reason: 'unsupported' };
  }
}


/**
 * Ask where to SAVE something, and under what name.
 *
 * Returns a path rather than writing anything: the dialog plugin gives a
 * destination, and the backend copies the file there. That avoids adding a
 * filesystem plugin and its capability for one button, and it keeps the write
 * on the side that already knows which file it is allowed to copy.
 */
export async function pickSavePath(suggested = 'paper.pdf') {
  if (!inTauri()) return { path: null, reason: 'unsupported' };

  try {
    const { save } = await import('@tauri-apps/plugin-dialog');
    const chosen = await save({
      title: 'Save the compiled PDF',
      defaultPath: suggested,
      filters: [{ name: 'PDF', extensions: ['pdf'] }],
    });
    if (!chosen) return { path: null, reason: 'cancelled' };
    return { path: typeof chosen === 'string' ? chosen : chosen.path, reason: 'ok' };
  } catch (err) {
    console.warn('[filePicker] save dialog unavailable:', err);
    return { path: null, reason: 'unsupported' };
  }
}
