"use client";
import { useFrame, useThree } from "@react-three/fiber";
import { useRef } from "react";
export function useCappedFrame(cb, max) {
  const last = useRef(performance.now());
  const { size } = useThree();
  const interval = 1e3 / (max ?? (size.width < 1024 ? 60 : 120));
  useFrame((st, delta) => {
    if (performance.now() - last.current > interval) {
      last.current = performance.now();
      cb(st, delta);
    }
  });
}
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsiPHN0ZGluPiJdLAogICJzb3VyY2VzQ29udGVudCI6IFsiJ3VzZSBjbGllbnQnXG5cbmltcG9ydCB7IHVzZUZyYW1lLCB1c2VUaHJlZSB9IGZyb20gJ0ByZWFjdC10aHJlZS9maWJlcidcbmltcG9ydCB0eXBlIHsgUmVuZGVyQ2FsbGJhY2sgfSBmcm9tICdAcmVhY3QtdGhyZWUvZmliZXInXG5pbXBvcnQgeyB1c2VSZWYgfSBmcm9tICdyZWFjdCdcblxuZXhwb3J0IGZ1bmN0aW9uIHVzZUNhcHBlZEZyYW1lKGNiOiBSZW5kZXJDYWxsYmFjaywgbWF4PzogbnVtYmVyKSB7XG4gIGNvbnN0IGxhc3QgPSB1c2VSZWYocGVyZm9ybWFuY2Uubm93KCkpXG4gIGNvbnN0IHsgc2l6ZSB9ID0gdXNlVGhyZWUoKVxuICBjb25zdCBpbnRlcnZhbCA9IDFlMyAvIChtYXggPz8gKHNpemUud2lkdGggPCAxMDI0ID8gNjAgOiAxMjApKVxuXG4gIHVzZUZyYW1lKChzdCwgZGVsdGEpID0+IHtcbiAgICBpZiAocGVyZm9ybWFuY2Uubm93KCkgLSBsYXN0LmN1cnJlbnQgPiBpbnRlcnZhbCkge1xuICAgICAgbGFzdC5jdXJyZW50ID0gcGVyZm9ybWFuY2Uubm93KClcbiAgICAgIGNiKHN0LCBkZWx0YSlcbiAgICB9XG4gIH0pXG59XG4iXSwKICAibWFwcGluZ3MiOiAiO0FBRUEsU0FBUyxVQUFVLGdCQUFnQjtBQUVuQyxTQUFTLGNBQWM7QUFFaEIsZ0JBQVMsZUFBZSxJQUFvQixLQUFjO0FBQy9ELFFBQU0sT0FBTyxPQUFPLFlBQVksSUFBSSxDQUFDO0FBQ3JDLFFBQU0sRUFBRSxLQUFLLElBQUksU0FBUztBQUMxQixRQUFNLFdBQVcsT0FBTyxRQUFRLEtBQUssUUFBUSxPQUFPLEtBQUs7QUFFekQsV0FBUyxDQUFDLElBQUksVUFBVTtBQUN0QixRQUFJLFlBQVksSUFBSSxJQUFJLEtBQUssVUFBVSxVQUFVO0FBQy9DLFdBQUssVUFBVSxZQUFZLElBQUk7QUFDL0IsU0FBRyxJQUFJLEtBQUs7QUFBQSxJQUNkO0FBQUEsRUFDRixDQUFDO0FBQ0g7IiwKICAibmFtZXMiOiBbXQp9Cg==
