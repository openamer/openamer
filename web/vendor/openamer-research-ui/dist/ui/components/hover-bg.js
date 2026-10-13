import { createElement } from "react";
import { cn, polyRef } from "../../utils/index.js";
export const HoverBg = polyRef(
  ({ as, className, ...rest }, ref) => createElement(as ?? "span", {
    ...rest,
    className: cn(
      "absolute inset-1 bg-midground pointer-events-none",
      "opacity-5 transition-opacity duration-250 group-hover:opacity-5 opacity-0 group-hover:duration-0",
      className
    ),
    ref
  })
);
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsiPHN0ZGluPiJdLAogICJzb3VyY2VzQ29udGVudCI6IFsiaW1wb3J0IHsgY3JlYXRlRWxlbWVudCB9IGZyb20gJ3JlYWN0J1xuXG5pbXBvcnQgeyBjbiwgcG9seVJlZiB9IGZyb20gJy4uLy4uL3V0aWxzJ1xuXG5leHBvcnQgY29uc3QgSG92ZXJCZyA9IHBvbHlSZWY8J3NwYW4nPigoeyBhcywgY2xhc3NOYW1lLCAuLi5yZXN0IH0sIHJlZikgPT5cbiAgY3JlYXRlRWxlbWVudCgoYXMgPz8gJ3NwYW4nKSBhcyBSZWFjdC5FbGVtZW50VHlwZSwge1xuICAgIC4uLnJlc3QsXG4gICAgY2xhc3NOYW1lOiBjbihcbiAgICAgICdhYnNvbHV0ZSBpbnNldC0xIGJnLW1pZGdyb3VuZCBwb2ludGVyLWV2ZW50cy1ub25lJyxcbiAgICAgICdvcGFjaXR5LTUgdHJhbnNpdGlvbi1vcGFjaXR5IGR1cmF0aW9uLTI1MCBncm91cC1ob3ZlcjpvcGFjaXR5LTUgb3BhY2l0eS0wIGdyb3VwLWhvdmVyOmR1cmF0aW9uLTAnLFxuICAgICAgY2xhc3NOYW1lXG4gICAgKSxcbiAgICByZWZcbiAgfSlcbilcbiJdLAogICJtYXBwaW5ncyI6ICJBQUFBLFNBQVMscUJBQXFCO0FBRTlCLFNBQVMsSUFBSSxlQUFlO0FBRXJCLGFBQU0sVUFBVTtBQUFBLEVBQWdCLENBQUMsRUFBRSxJQUFJLFdBQVcsR0FBRyxLQUFLLEdBQUcsUUFDbEUsY0FBZSxNQUFNLFFBQThCO0FBQUEsSUFDakQsR0FBRztBQUFBLElBQ0gsV0FBVztBQUFBLE1BQ1Q7QUFBQSxNQUNBO0FBQUEsTUFDQTtBQUFBLElBQ0Y7QUFBQSxJQUNBO0FBQUEsRUFDRixDQUFDO0FBQ0g7IiwKICAibmFtZXMiOiBbXQp9Cg==
