import { cva } from "class-variance-authority";
import { createElement } from "react";
import { cn, polyRef } from "../../../utils/index.js";
const typographyVariants = cva("font-sans", {
  variants: {
    compressed: { true: "font-compressed" },
    courier: { true: "font-courier" },
    expanded: { true: "font-expanded" },
    mondwest: { true: "font-mondwest tracking-[0.1875rem]" },
    mono: { true: "font-mono" },
    sans: { true: "font-sans" },
    variant: {
      lg: "text-[2.625rem] leading-[1] tracking-[0.0525rem]",
      md: "text-[2.625rem] leading-[1] tracking-[0.0525rem]",
      sm: "leading-1.4 text-[.9375rem] tracking-[0.1875rem]",
      xl: "text-[4.5rem] leading-[1] tracking-[0.135rem]"
    }
  }
});
export const Typography = polyRef(
  ({
    as,
    className,
    compressed,
    courier,
    expanded,
    mondwest,
    mono,
    variant,
    ...rest
  }, ref) => {
    const fonts = { compressed, courier, expanded, mondwest, mono };
    const fontVariant = { ...fonts, sans: !Object.values(fonts).some(Boolean) };
    return createElement(as ?? "span", {
      ...rest,
      className: cn(typographyVariants({ ...fontVariant, variant }), className),
      ref
    });
  }
);
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsiPHN0ZGluPiJdLAogICJzb3VyY2VzQ29udGVudCI6IFsiaW1wb3J0IHsgY3ZhLCB0eXBlIFZhcmlhbnRQcm9wcyB9IGZyb20gJ2NsYXNzLXZhcmlhbmNlLWF1dGhvcml0eSdcbmltcG9ydCB7IGNyZWF0ZUVsZW1lbnQgfSBmcm9tICdyZWFjdCdcblxuaW1wb3J0IHsgY24sIHR5cGUgUG9seVByb3BzLCBwb2x5UmVmIH0gZnJvbSAnLi4vLi4vLi4vdXRpbHMnXG5cbmNvbnN0IHR5cG9ncmFwaHlWYXJpYW50cyA9IGN2YSgnZm9udC1zYW5zJywge1xuICB2YXJpYW50czoge1xuICAgIGNvbXByZXNzZWQ6IHsgdHJ1ZTogJ2ZvbnQtY29tcHJlc3NlZCcgfSxcbiAgICBjb3VyaWVyOiB7IHRydWU6ICdmb250LWNvdXJpZXInIH0sXG4gICAgZXhwYW5kZWQ6IHsgdHJ1ZTogJ2ZvbnQtZXhwYW5kZWQnIH0sXG4gICAgbW9uZHdlc3Q6IHsgdHJ1ZTogJ2ZvbnQtbW9uZHdlc3QgdHJhY2tpbmctWzAuMTg3NXJlbV0nIH0sXG4gICAgbW9ubzogeyB0cnVlOiAnZm9udC1tb25vJyB9LFxuICAgIHNhbnM6IHsgdHJ1ZTogJ2ZvbnQtc2FucycgfSxcbiAgICB2YXJpYW50OiB7XG4gICAgICBsZzogJ3RleHQtWzIuNjI1cmVtXSBsZWFkaW5nLVsxXSB0cmFja2luZy1bMC4wNTI1cmVtXScsXG4gICAgICBtZDogJ3RleHQtWzIuNjI1cmVtXSBsZWFkaW5nLVsxXSB0cmFja2luZy1bMC4wNTI1cmVtXScsXG4gICAgICBzbTogJ2xlYWRpbmctMS40IHRleHQtWy45Mzc1cmVtXSB0cmFja2luZy1bMC4xODc1cmVtXScsXG4gICAgICB4bDogJ3RleHQtWzQuNXJlbV0gbGVhZGluZy1bMV0gdHJhY2tpbmctWzAuMTM1cmVtXSdcbiAgICB9XG4gIH1cbn0pXG5cbmV4cG9ydCBjb25zdCBUeXBvZ3JhcGh5ID0gcG9seVJlZjwnc3BhbicsIE93blByb3BzPihcbiAgKFxuICAgIHtcbiAgICAgIGFzLFxuICAgICAgY2xhc3NOYW1lLFxuICAgICAgY29tcHJlc3NlZCxcbiAgICAgIGNvdXJpZXIsXG4gICAgICBleHBhbmRlZCxcbiAgICAgIG1vbmR3ZXN0LFxuICAgICAgbW9ubyxcbiAgICAgIHZhcmlhbnQsXG4gICAgICAuLi5yZXN0XG4gICAgfSxcbiAgICByZWZcbiAgKSA9PiB7XG4gICAgY29uc3QgZm9udHMgPSB7IGNvbXByZXNzZWQsIGNvdXJpZXIsIGV4cGFuZGVkLCBtb25kd2VzdCwgbW9ubyB9XG4gICAgY29uc3QgZm9udFZhcmlhbnQgPSB7IC4uLmZvbnRzLCBzYW5zOiAhT2JqZWN0LnZhbHVlcyhmb250cykuc29tZShCb29sZWFuKSB9XG5cbiAgICByZXR1cm4gY3JlYXRlRWxlbWVudCgoYXMgPz8gJ3NwYW4nKSBhcyBSZWFjdC5FbGVtZW50VHlwZSwge1xuICAgICAgLi4ucmVzdCxcbiAgICAgIGNsYXNzTmFtZTogY24odHlwb2dyYXBoeVZhcmlhbnRzKHsgLi4uZm9udFZhcmlhbnQsIHZhcmlhbnQgfSksIGNsYXNzTmFtZSksXG4gICAgICByZWZcbiAgICB9KVxuICB9XG4pXG5cbnR5cGUgT3duUHJvcHMgPSBWYXJpYW50UHJvcHM8dHlwZW9mIHR5cG9ncmFwaHlWYXJpYW50cz5cblxuZXhwb3J0IHR5cGUgVHlwb2dyYXBoeVByb3BzPFQgZXh0ZW5kcyBSZWFjdC5FbGVtZW50VHlwZSA9ICdzcGFuJz4gPSBQb2x5UHJvcHM8XG4gIFQsXG4gIE93blByb3BzXG4+XG4iXSwKICAibWFwcGluZ3MiOiAiQUFBQSxTQUFTLFdBQThCO0FBQ3ZDLFNBQVMscUJBQXFCO0FBRTlCLFNBQVMsSUFBb0IsZUFBZTtBQUU1QyxNQUFNLHFCQUFxQixJQUFJLGFBQWE7QUFBQSxFQUMxQyxVQUFVO0FBQUEsSUFDUixZQUFZLEVBQUUsTUFBTSxrQkFBa0I7QUFBQSxJQUN0QyxTQUFTLEVBQUUsTUFBTSxlQUFlO0FBQUEsSUFDaEMsVUFBVSxFQUFFLE1BQU0sZ0JBQWdCO0FBQUEsSUFDbEMsVUFBVSxFQUFFLE1BQU0scUNBQXFDO0FBQUEsSUFDdkQsTUFBTSxFQUFFLE1BQU0sWUFBWTtBQUFBLElBQzFCLE1BQU0sRUFBRSxNQUFNLFlBQVk7QUFBQSxJQUMxQixTQUFTO0FBQUEsTUFDUCxJQUFJO0FBQUEsTUFDSixJQUFJO0FBQUEsTUFDSixJQUFJO0FBQUEsTUFDSixJQUFJO0FBQUEsSUFDTjtBQUFBLEVBQ0Y7QUFDRixDQUFDO0FBRU0sYUFBTSxhQUFhO0FBQUEsRUFDeEIsQ0FDRTtBQUFBLElBQ0U7QUFBQSxJQUNBO0FBQUEsSUFDQTtBQUFBLElBQ0E7QUFBQSxJQUNBO0FBQUEsSUFDQTtBQUFBLElBQ0E7QUFBQSxJQUNBO0FBQUEsSUFDQSxHQUFHO0FBQUEsRUFDTCxHQUNBLFFBQ0c7QUFDSCxVQUFNLFFBQVEsRUFBRSxZQUFZLFNBQVMsVUFBVSxVQUFVLEtBQUs7QUFDOUQsVUFBTSxjQUFjLEVBQUUsR0FBRyxPQUFPLE1BQU0sQ0FBQyxPQUFPLE9BQU8sS0FBSyxFQUFFLEtBQUssT0FBTyxFQUFFO0FBRTFFLFdBQU8sY0FBZSxNQUFNLFFBQThCO0FBQUEsTUFDeEQsR0FBRztBQUFBLE1BQ0gsV0FBVyxHQUFHLG1CQUFtQixFQUFFLEdBQUcsYUFBYSxRQUFRLENBQUMsR0FBRyxTQUFTO0FBQUEsTUFDeEU7QUFBQSxJQUNGLENBQUM7QUFBQSxFQUNIO0FBQ0Y7IiwKICAibmFtZXMiOiBbXQp9Cg==
