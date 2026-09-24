import "@testing-library/jest-dom/vitest";
import { afterEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); try { localStorage.clear(); } catch { /* */ } });

// jsdom lacks these browser APIs used by framer-motion / scrolling
class IO { observe() {} unobserve() {} disconnect() {} takeRecords() { return []; } root = null; rootMargin = ""; thresholds = []; }
(globalThis as unknown as { IntersectionObserver: unknown }).IntersectionObserver = IO;
window.matchMedia = window.matchMedia || ((q: string) => ({ matches: false, media: q, onchange: null, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {}, dispatchEvent: () => false })) as unknown as typeof window.matchMedia;
Element.prototype.scrollIntoView = Element.prototype.scrollIntoView || (() => {});
