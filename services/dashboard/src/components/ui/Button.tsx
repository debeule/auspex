const VARIANTS = {
  primary: 'bg-blue-600 text-white hover:bg-blue-700 disabled:bg-blue-300',
  secondary: 'border border-gray-300 bg-white text-gray-800 hover:bg-gray-50',
  danger: 'bg-red-600 text-white hover:bg-red-700 disabled:bg-red-300',
};

export default function Button({
  variant = 'primary',
  className = '',
  ...props
}: React.ComponentProps<'button'> & { variant?: keyof typeof VARIANTS }) {
  return (
    <button
      type="button"
      {...props}
      className={`rounded px-3 py-1.5 text-sm font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${VARIANTS[variant]} ${className}`}
    />
  );
}
