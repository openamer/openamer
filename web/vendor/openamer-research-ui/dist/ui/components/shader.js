"use client";
import { jsx, jsxs } from "react/jsx-runtime";
import { useThree } from "@react-three/fiber";
import { useEffect, useRef } from "react";
import * as THREE from "three";
import { useCappedFrame } from "../../hooks/use-capped-frame.js";
const defaultUniforms = {
  uResolution: new THREE.Uniform(new THREE.Vector4()),
  uTime: new THREE.Uniform(0)
};
export function Shader({
  children,
  defines,
  depthTest,
  fragmentShader,
  uniforms,
  vertexShader,
  ...props
}) {
  const invalidate = useThree((st) => st.invalidate);
  const { size, viewport } = useThree();
  const isMobile = size.width < 1024;
  const uniformsRef = useRef({
    ...defaultUniforms,
    ...uniforms ?? {}
  });
  useCappedFrame(
    ({ clock }) => {
      const w = size.width * viewport.dpr;
      const h = size.height * viewport.dpr;
      uniformsRef.current.uTime.value = clock.getElapsedTime();
      uniformsRef.current.uResolution.value.copy(
        new THREE.Vector4(w, h, w / h, viewport.dpr)
      );
    },
    isMobile ? 0 : 80
  );
  useEffect(
    () => void (uniforms && Object.assign(uniformsRef.current, uniforms)),
    [uniforms]
  );
  useEffect(() => void (isMobile && invalidate(80)), [invalidate, isMobile]);
  const materialProps = {
    defines: defines ?? {},
    depthTest,
    fragmentShader,
    side: THREE.DoubleSide,
    transparent: true,
    uniforms: uniformsRef.current,
    vertexShader
  };
  if (typeof children === "function") {
    return children(/* @__PURE__ */ jsx("shaderMaterial", { ...materialProps }));
  }
  return /* @__PURE__ */ jsxs("mesh", { ...props, children: [
    children ?? /* @__PURE__ */ jsx("planeGeometry", {}),
    /* @__PURE__ */ jsx("shaderMaterial", { ...materialProps })
  ] });
}
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsiPHN0ZGluPiJdLAogICJzb3VyY2VzQ29udGVudCI6IFsiJ3VzZSBjbGllbnQnXG5cbmltcG9ydCB7IHR5cGUgVGhyZWVFbGVtZW50cywgdXNlVGhyZWUgfSBmcm9tICdAcmVhY3QtdGhyZWUvZmliZXInXG5pbXBvcnQgeyB1c2VFZmZlY3QsIHVzZVJlZiB9IGZyb20gJ3JlYWN0J1xuaW1wb3J0IHR5cGUgeyBSZWFjdE5vZGUgfSBmcm9tICdyZWFjdCdcbmltcG9ydCAqIGFzIFRIUkVFIGZyb20gJ3RocmVlJ1xuXG5pbXBvcnQgeyB1c2VDYXBwZWRGcmFtZSB9IGZyb20gJy4uLy4uL2hvb2tzL3VzZS1jYXBwZWQtZnJhbWUnXG5cbmNvbnN0IGRlZmF1bHRVbmlmb3JtcyA9IHtcbiAgdVJlc29sdXRpb246IG5ldyBUSFJFRS5Vbmlmb3JtKG5ldyBUSFJFRS5WZWN0b3I0KCkpLFxuICB1VGltZTogbmV3IFRIUkVFLlVuaWZvcm0oMClcbn1cblxuZXhwb3J0IGZ1bmN0aW9uIFNoYWRlcih7XG4gIGNoaWxkcmVuLFxuICBkZWZpbmVzLFxuICBkZXB0aFRlc3QsXG4gIGZyYWdtZW50U2hhZGVyLFxuICB1bmlmb3JtcyxcbiAgdmVydGV4U2hhZGVyLFxuICAuLi5wcm9wc1xufTogU2hhZGVyUHJvcHMpIHtcbiAgY29uc3QgaW52YWxpZGF0ZSA9IHVzZVRocmVlKHN0ID0+IHN0LmludmFsaWRhdGUpXG4gIGNvbnN0IHsgc2l6ZSwgdmlld3BvcnQgfSA9IHVzZVRocmVlKClcblxuICBjb25zdCBpc01vYmlsZSA9IHNpemUud2lkdGggPCAxMDI0XG5cbiAgY29uc3QgdW5pZm9ybXNSZWYgPSB1c2VSZWYoe1xuICAgIC4uLmRlZmF1bHRVbmlmb3JtcyxcbiAgICAuLi4odW5pZm9ybXMgPz8ge30pXG4gIH0pXG5cbiAgdXNlQ2FwcGVkRnJhbWUoXG4gICAgKHsgY2xvY2sgfSkgPT4ge1xuICAgICAgY29uc3QgdyA9IHNpemUud2lkdGggKiB2aWV3cG9ydC5kcHJcbiAgICAgIGNvbnN0IGggPSBzaXplLmhlaWdodCAqIHZpZXdwb3J0LmRwclxuXG4gICAgICB1bmlmb3Jtc1JlZi5jdXJyZW50LnVUaW1lLnZhbHVlID0gY2xvY2suZ2V0RWxhcHNlZFRpbWUoKVxuICAgICAgdW5pZm9ybXNSZWYuY3VycmVudC51UmVzb2x1dGlvbi52YWx1ZS5jb3B5KFxuICAgICAgICBuZXcgVEhSRUUuVmVjdG9yNCh3LCBoLCB3IC8gaCwgdmlld3BvcnQuZHByKVxuICAgICAgKVxuICAgIH0sXG4gICAgaXNNb2JpbGUgPyAwIDogODBcbiAgKVxuXG4gIHVzZUVmZmVjdChcbiAgICAoKSA9PiB2b2lkICh1bmlmb3JtcyAmJiBPYmplY3QuYXNzaWduKHVuaWZvcm1zUmVmLmN1cnJlbnQsIHVuaWZvcm1zKSksXG4gICAgW3VuaWZvcm1zXVxuICApXG5cbiAgdXNlRWZmZWN0KCgpID0+IHZvaWQgKGlzTW9iaWxlICYmIGludmFsaWRhdGUoODApKSwgW2ludmFsaWRhdGUsIGlzTW9iaWxlXSlcblxuICBjb25zdCBtYXRlcmlhbFByb3BzID0ge1xuICAgIGRlZmluZXM6IGRlZmluZXMgPz8ge30sXG4gICAgZGVwdGhUZXN0LFxuICAgIGZyYWdtZW50U2hhZGVyLFxuICAgIHNpZGU6IFRIUkVFLkRvdWJsZVNpZGUsXG4gICAgdHJhbnNwYXJlbnQ6IHRydWUsXG4gICAgdW5pZm9ybXM6IHVuaWZvcm1zUmVmLmN1cnJlbnQsXG4gICAgdmVydGV4U2hhZGVyXG4gIH0gc2F0aXNmaWVzIFRocmVlRWxlbWVudHNbJ3NoYWRlck1hdGVyaWFsJ11cblxuICBpZiAodHlwZW9mIGNoaWxkcmVuID09PSAnZnVuY3Rpb24nKSB7XG4gICAgcmV0dXJuIGNoaWxkcmVuKDxzaGFkZXJNYXRlcmlhbCB7Li4ubWF0ZXJpYWxQcm9wc30gLz4pXG4gIH1cblxuICByZXR1cm4gKFxuICAgIDxtZXNoIHsuLi5wcm9wc30+XG4gICAgICB7Y2hpbGRyZW4gPz8gPHBsYW5lR2VvbWV0cnkgLz59XG4gICAgICA8c2hhZGVyTWF0ZXJpYWwgey4uLm1hdGVyaWFsUHJvcHN9IC8+XG4gICAgPC9tZXNoPlxuICApXG59XG5cbmludGVyZmFjZSBTaGFkZXJQcm9wc1xuICBleHRlbmRzIE9taXQ8VGhyZWVFbGVtZW50c1snbWVzaCddLCAnY2hpbGRyZW4nPixcbiAgICBQaWNrPFxuICAgICAgVGhyZWVFbGVtZW50c1snc2hhZGVyTWF0ZXJpYWwnXSxcbiAgICAgICdkZWZpbmVzJyB8ICdkZXB0aFRlc3QnIHwgJ2ZyYWdtZW50U2hhZGVyJyB8ICd1bmlmb3JtcycgfCAndmVydGV4U2hhZGVyJ1xuICAgID4ge1xuICBjaGlsZHJlbj86ICgobWF0ZXJpYWw6IFJlYWN0Tm9kZSkgPT4gUmVhY3ROb2RlKSB8IFJlYWN0Tm9kZVxufVxuIl0sCiAgIm1hcHBpbmdzIjogIjtBQWdFb0IsY0FJaEIsWUFKZ0I7QUE5RHBCLFNBQTZCLGdCQUFnQjtBQUM3QyxTQUFTLFdBQVcsY0FBYztBQUVsQyxZQUFZLFdBQVc7QUFFdkIsU0FBUyxzQkFBc0I7QUFFL0IsTUFBTSxrQkFBa0I7QUFBQSxFQUN0QixhQUFhLElBQUksTUFBTSxRQUFRLElBQUksTUFBTSxRQUFRLENBQUM7QUFBQSxFQUNsRCxPQUFPLElBQUksTUFBTSxRQUFRLENBQUM7QUFDNUI7QUFFTyxnQkFBUyxPQUFPO0FBQUEsRUFDckI7QUFBQSxFQUNBO0FBQUEsRUFDQTtBQUFBLEVBQ0E7QUFBQSxFQUNBO0FBQUEsRUFDQTtBQUFBLEVBQ0EsR0FBRztBQUNMLEdBQWdCO0FBQ2QsUUFBTSxhQUFhLFNBQVMsUUFBTSxHQUFHLFVBQVU7QUFDL0MsUUFBTSxFQUFFLE1BQU0sU0FBUyxJQUFJLFNBQVM7QUFFcEMsUUFBTSxXQUFXLEtBQUssUUFBUTtBQUU5QixRQUFNLGNBQWMsT0FBTztBQUFBLElBQ3pCLEdBQUc7QUFBQSxJQUNILEdBQUksWUFBWSxDQUFDO0FBQUEsRUFDbkIsQ0FBQztBQUVEO0FBQUEsSUFDRSxDQUFDLEVBQUUsTUFBTSxNQUFNO0FBQ2IsWUFBTSxJQUFJLEtBQUssUUFBUSxTQUFTO0FBQ2hDLFlBQU0sSUFBSSxLQUFLLFNBQVMsU0FBUztBQUVqQyxrQkFBWSxRQUFRLE1BQU0sUUFBUSxNQUFNLGVBQWU7QUFDdkQsa0JBQVksUUFBUSxZQUFZLE1BQU07QUFBQSxRQUNwQyxJQUFJLE1BQU0sUUFBUSxHQUFHLEdBQUcsSUFBSSxHQUFHLFNBQVMsR0FBRztBQUFBLE1BQzdDO0FBQUEsSUFDRjtBQUFBLElBQ0EsV0FBVyxJQUFJO0FBQUEsRUFDakI7QUFFQTtBQUFBLElBQ0UsTUFBTSxNQUFNLFlBQVksT0FBTyxPQUFPLFlBQVksU0FBUyxRQUFRO0FBQUEsSUFDbkUsQ0FBQyxRQUFRO0FBQUEsRUFDWDtBQUVBLFlBQVUsTUFBTSxNQUFNLFlBQVksV0FBVyxFQUFFLElBQUksQ0FBQyxZQUFZLFFBQVEsQ0FBQztBQUV6RSxRQUFNLGdCQUFnQjtBQUFBLElBQ3BCLFNBQVMsV0FBVyxDQUFDO0FBQUEsSUFDckI7QUFBQSxJQUNBO0FBQUEsSUFDQSxNQUFNLE1BQU07QUFBQSxJQUNaLGFBQWE7QUFBQSxJQUNiLFVBQVUsWUFBWTtBQUFBLElBQ3RCO0FBQUEsRUFDRjtBQUVBLE1BQUksT0FBTyxhQUFhLFlBQVk7QUFDbEMsV0FBTyxTQUFTLG9CQUFDLG9CQUFnQixHQUFHLGVBQWUsQ0FBRTtBQUFBLEVBQ3ZEO0FBRUEsU0FDRSxxQkFBQyxVQUFNLEdBQUcsT0FDUDtBQUFBLGdCQUFZLG9CQUFDLG1CQUFjO0FBQUEsSUFDNUIsb0JBQUMsb0JBQWdCLEdBQUcsZUFBZTtBQUFBLEtBQ3JDO0FBRUo7IiwKICAibmFtZXMiOiBbXQp9Cg==
