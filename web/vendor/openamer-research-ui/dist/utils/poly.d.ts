export type PolyProps<T extends React.ElementType, Own extends object = object> = {
    as?: T;
} & Own & Omit<React.ComponentPropsWithoutRef<T>, 'as' | keyof Own>;
export type PolyRef<T extends React.ElementType> = React.ComponentPropsWithRef<T>['ref'];
export type PolyComponent<D extends React.ElementType, Own extends object = object> = <T extends React.ElementType = D>(props: PolyProps<T, Own> & {
    ref?: PolyRef<T>;
}) => null | React.ReactElement;
export declare const polyRef: <D extends React.ElementType, Own extends object = object>(render: <T extends React.ElementType = D>(props: PolyProps<T, Own>, ref: PolyRef<T>) => null | React.ReactElement) => PolyComponent<D, Own>;
