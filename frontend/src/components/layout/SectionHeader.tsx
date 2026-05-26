import React from 'react';

interface SectionHeaderProps {
  title: string;
  count?: number;
  actions?: React.ReactNode;
}

export const SectionHeader: React.FC<SectionHeaderProps> = ({ title, count, actions }) => {
  return (
    <div className="flex justify-between items-end border-b border-slate-200 pb-2 mb-4 mt-8 first:mt-0">
      <div className="flex items-center gap-2">
        <h2 className="text-lg font-semibold text-slate-800">{title}</h2>
        {count !== undefined && (
          <span className="bg-slate-100 text-slate-600 px-2 py-0.5 rounded-full text-xs font-bold">
            {count}
          </span>
        )}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
};
