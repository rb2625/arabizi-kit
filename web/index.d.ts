/** Type declarations for arabizikit (browser and Node). */

export interface Candidate {
  /** Arabic-script rendering of one word or sentence. */
  ar: string;
  /** Lower is better; small non-negative penalty. */
  score: number;
}

export interface Evidence {
  arabizi: string;
  ar: string;
  dialect: string;
}

export interface DialectGuess {
  dialect: string;
  confidence: number;
  evidence: Evidence[];
}

export interface Token {
  kind: "space" | "latin" | "other" | "word" | "article" | "conj" | "contraction";
  raw: string;
  candidates?: Candidate[];
  evidence?: Evidence[];
}

export interface TransliterateOptions {
  /** Number of ranked full-sentence candidates (default 3). */
  topK?: number;
  /** Return the detected dialect (default false). */
  withDialect?: boolean;
  /** Assume a dialect convention for ambiguous readings: egyptian, levantine, gulf, maghrebi. */
  dialectHint?: string;
}

export interface TransliterateResult {
  /** Top-1 rendering, preserving the original spacing and punctuation. */
  text: string;
  /** Top-k full-sentence candidates, ascending score. */
  candidates: Candidate[];
  /** Dialect guess when withDialect is set, otherwise null. */
  dialect: DialectGuess | null;
  /** Per-word lexicon evidence collected while transliterating. */
  evidence: Evidence[];
}

/** Transliterate an Arabizi string to Arabic script. */
export declare function transliterate(text: string, options?: TransliterateOptions): TransliterateResult;

/** Split text into space, latin, and other tokens. */
export declare function tokenize(text: string): Token[];

/** Process one latin word into its ranked candidate readings. */
export declare function processWord(word: string, dialectHint?: string): Token;
