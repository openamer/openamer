import { type ClassValue } from 'clsx';
import * as THREE from 'three';
import { hexToRgb, rgbToHex } from './color';
import { polyRef } from './poly';
import type { PolyComponent, PolyProps, PolyRef } from './poly';
export { hexToRgb, polyRef, rgbToHex };
export type { PolyComponent, PolyProps, PolyRef };
export declare const cn: (...inputs: ClassValue[]) => string;
export declare const clamp: (v: number, min?: number, max?: number) => number;
export declare const smoothstep: (edge0: number, edge1: number, x: number) => number;
export declare const hexToVec3: (hex: string) => THREE.Vector3;
export declare const truncate: (text: string, options: {
    length: number;
}) => string;
export declare const stripWpStyles: (html: string) => string;
