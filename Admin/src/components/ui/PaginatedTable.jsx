import { useState, useMemo } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';

export function Table({ children, className = "", ...rest }) {
  return (
    <div className={["overflow-hidden rounded-lg border border-(--border) bg-white shadow-[0_12px_30px_var(--shadow-sm)]", className].join(" ")}>
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
    <tr className={["border-t border-(--border) transition hover:bg-(--bg)", className].join(" ")} {...rest}>
      {children}
    </tr>
  );
}

export function TableHeadCell({ children, className = "", ...rest }) {
  return (
    <th
      className={[
        "px-5 py-3.75 text-xs font-bold uppercase tracking-[0.6px] text-(--text-light)",
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
    <td className={["text-(--text) align-top", className].join(" ")} style={{ padding: '18px 20px', fontSize: '14px', verticalAlign: 'top' }} {...rest}>
      {children}
    </td>
  );
}

/**
 * PaginatedTable wrapper component
 * @param {Array} data - Array of items to paginate
 * @param {number} itemsPerPage - Items per page (default 10)
 * @param {Function} renderRow - Function to render each row (receives item and key)
 * @param {React.ReactNode} children - Table head JSX
 * @param {string} emptyMessage - Message when no data
 */
export function PaginatedTable({ data = [], itemsPerPage = 10, renderRow, children, emptyMessage = 'No data available' }) {
  const [currentPage, setCurrentPage] = useState(1);

  const { paginatedData, totalPages } = useMemo(() => {
    const total = Math.ceil(data.length / itemsPerPage);
    const start = (currentPage - 1) * itemsPerPage;
    const end = start + itemsPerPage;
    return {
      paginatedData: data.slice(start, end),
      totalPages: total,
    };
  }, [data, currentPage, itemsPerPage]);

  const goToPrevious = () => setCurrentPage((p) => Math.max(p - 1, 1));
  const goToNext = () => setCurrentPage((p) => Math.min(p + 1, totalPages));
  const goToPage = (page) => setCurrentPage(Math.max(1, Math.min(page, totalPages)));

  if (data.length === 0) {
    return (
      <div className="overflow-hidden rounded-lg border border-(--border) bg-white shadow-sm p-6 text-center">
        <p className="text-(--text-light) text-sm">{emptyMessage}</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <Table>
        {children}
        <TableBody>
          {paginatedData.map((item, idx) => renderRow(item, idx))}
        </TableBody>
      </Table>

      {/* Pagination Controls */}
      <div className="flex items-center justify-between px-4 py-3 bg-white border border-(--border) rounded-lg">
        <div className="text-xs text-(--text-light)">
          Page <span className="font-semibold text-(--primary)">{currentPage}</span> of{' '}
          <span className="font-semibold text-(--primary)">{totalPages}</span>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={goToPrevious}
            disabled={currentPage === 1}
            className="p-1.5 rounded-md border border-(--border) bg-white hover:bg-(--bg) disabled:opacity-50 disabled:cursor-not-allowed transition"
          >
            <ChevronLeft size={16} className="text-(--text-light)" />
          </button>

          <div className="flex gap-1">
            {Array.from({ length: totalPages }, (_, i) => i + 1).map((page) => (
              <button
                key={page}
                onClick={() => goToPage(page)}
                className={[
                  'px-2.5 py-1 rounded-md text-xs font-medium transition',
                  currentPage === page
                    ? 'bg-(--primary) text-white'
                    : 'bg-white border border-(--border) text-(--text) hover:bg-(--bg)',
                ].join(' ')}
              >
                {page}
              </button>
            ))}
          </div>

          <button
            onClick={goToNext}
            disabled={currentPage === totalPages}
            className="p-1.5 rounded-md border border-(--border) bg-white hover:bg-(--bg) disabled:opacity-50 disabled:cursor-not-allowed transition"
          >
            <ChevronRight size={16} className="text-(--text-light)" />
          </button>
        </div>

        <div className="text-xs text-(--text-light)">
          Total: <span className="font-semibold text-(--primary)">{data.length}</span> items
        </div>
      </div>
    </div>
  );
}

export default PaginatedTable;
