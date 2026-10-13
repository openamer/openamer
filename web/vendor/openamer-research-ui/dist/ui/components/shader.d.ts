import { type ThreeElements } from '@react-three/fiber';
import type { ReactNode } from 'react';
export declare function Shader({ children, defines, depthTest, fragmentShader, uniforms, vertexShader, ...props }: ShaderProps): string | number | bigint | boolean | Iterable<ReactNode> | Promise<string | number | bigint | boolean | import("react").ReactPortal | import("react").ReactElement<unknown, string | import("react").JSXElementConstructor<any>> | Iterable<ReactNode> | null | undefined> | import("react").JSX.Element | null | undefined;
interface ShaderProps extends Omit<ThreeElements['mesh'], 'children'>, Pick<ThreeElements['shaderMaterial'], 'defines' | 'depthTest' | 'fragmentShader' | 'uniforms' | 'vertexShader'> {
    children?: ((material: ReactNode) => ReactNode) | ReactNode;
}
export {};
