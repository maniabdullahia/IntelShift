export function Table({ children, className = "", ...rest }) {
  return (
    <div
      className={[
        "overflow-hidden rounded-lg border border-(--border) bg-white shadow-[0_12px_30px_var(--shadow-sm)]",
        className,
      ].join(" ")}
    >
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-left" {...rest}>
          {children}
        </table>
      </div>
    </div>
  );
}

export function TableHead({ children, className = "", ...rest }) {
  return (
    <thead className={["bg-(--bg)", className].join(" ")} {...rest}>
      {children}
    </thead>
  );
}

export function TableBody({ children, className = "", ...rest }) {
  return (
    <tbody className={className} {...rest}>
      {children}
    </tbody>
  );
}

export function TableRow({ children, className = "", ...rest }) {
  return (
    <tr
      className={[
        "border-t border-(--border) transition hover:bg-(--bg)",
        className,
      ].join(" ")}
      {...rest}
    >
      {children}
    </tr>
  );
}

export function TableHeadCell({ children, className = "", ...rest }) {
  return (
    <th
      className={[
        "text-xs font-bold uppercase text-(--text-light) px-5 py-3.75 tracking-[0.6px]",
        className,
      ].join(" ")}
      {...rest}
    >
      {children}
    </th>
  );
}

export function TableCell({ children, className = "", ...rest }) {
  return (
    <td
      className={["text-(--text) align-top text-[14px] py-4.5 px-5", className].join(" ")}
      {...rest}
    >
      {children}
    </td>
  );
}

export default Table;
