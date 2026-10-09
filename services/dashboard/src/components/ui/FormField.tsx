/** A labelled input; the label is tied to the input so it is the input's accessible name. */
export default function FormField({
  id,
  label,
  ...inputProps
}: React.InputHTMLAttributes<HTMLInputElement> & { id: string; label: string }) {
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-sm font-medium text-gray-700">
        {label}
      </label>
      <input
        id={id}
        {...inputProps}
        className="rounded border border-gray-300 px-2 py-1.5 text-sm focus:border-blue-500 focus:outline-none"
      />
    </div>
  );
}
