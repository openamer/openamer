export function LayoutWrapper({
  children
}: Readonly<React.PropsWithChildren>) {
  return (
    <html lang="en">
      <body className="text-text-primary bg-black antialiased">
        {children}
      </body>
    </html>
  )
}
