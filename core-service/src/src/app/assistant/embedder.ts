/**
 * Query embedder – runs all-MiniLM-L6-v2 (ONNX) inside Node.js via
 * @xenova/transformers.  The same model is used by Python's FastEmbed to
 * index assistant_chunks, so the vector spaces are compatible and pgvector's
 * <=> cosine operator works correctly.
 *
 * ts-node compiles dynamic import() to require() in CJS mode, which breaks
 * ESM-only packages like @xenova/transformers.  We hide the import inside
 * new Function() so ts-node never touches it.
 */

const MODEL = 'Xenova/all-MiniLM-L6-v2';

let _extractor: any = null;
let _loading: Promise<any> | null = null;

async function getExtractor(): Promise<any> {
  if (_extractor) return _extractor;
  if (_loading) return _loading;

  _loading = (async () => {
    // new Function() is opaque to ts-node's CJS transpiler, so the real
    // ESM import() reaches Node's module loader unchanged.
    const { pipeline, env } = await (new Function('pkg', 'return import(pkg)'))('@xenova/transformers');
    env.cacheDir = './.model-cache';
    const p = await pipeline('feature-extraction', MODEL, { quantized: true });
    _extractor = p;
    _loading = null;
    console.log('[embedder] all-MiniLM-L6-v2 loaded');
    return p;
  })().catch((err: any) => {
    _loading = null;
    throw err;
  });

  return _loading;
}

/**
 * Embed a single text string.
 * Returns a 384-dim Float32 array, or null if the model fails to load.
 */
export async function embedText(text: string): Promise<number[] | null> {
  try {
    const extractor = await getExtractor();
    const output = await extractor(text, { pooling: 'mean', normalize: true });
    return Array.from(output.data) as number[];
  } catch (err) {
    console.error('[embedder] embed failed:', err);
    return null;
  }
}

/**
 * Warm up the model at app startup so the first user query isn't slow.
 * Call this once from your server entry point (fire-and-forget is fine).
 */
export function warmupEmbedder(): void {
  getExtractor().catch((err: any) =>
    console.error('[embedder] warmup failed:', err)
  );
}
