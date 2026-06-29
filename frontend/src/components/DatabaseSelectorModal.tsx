import React, { useState, useMemo } from 'react';
import { Search, X } from 'lucide-react';
import { DATABASE_LIST } from '../config/databases';
import type { DatabaseConfig } from '../config/databases';

interface DatabaseSelectorModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelect: (db: DatabaseConfig) => void;
}

export const DatabaseSelectorModal: React.FC<DatabaseSelectorModalProps> = ({
  isOpen,
  onClose,
  onSelect,
}) => {
  const [searchTerm, setSearchTerm] = useState('');

  const filteredDatabases = useMemo(() => {
    if (!searchTerm.trim()) {
      return DATABASE_LIST;
    }
    const lowerSearch = searchTerm.toLowerCase();
    return DATABASE_LIST.filter(
      (db) =>
        db.name.toLowerCase().includes(lowerSearch) ||
        db.category.toLowerCase().includes(lowerSearch)
    );
  }, [searchTerm]);

  const categories = useMemo(() => {
    const cats = new Set<string>();
    filteredDatabases.forEach((db) => cats.add(db.category));
    return Array.from(cats);
  }, [filteredDatabases]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-slate-900/60 backdrop-blur-sm transition-opacity"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative w-full max-w-3xl bg-white dark:bg-[#081120] border border-slate-200 dark:border-cyan-900/40 rounded-3xl shadow-[0_0_40px_rgba(0,229,255,0.15)] flex flex-col max-h-[85vh] overflow-hidden transform transition-all">
        {/* Header & Search */}
        <div className="p-6 border-b border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-[#0F172A]/50">
          <div className="flex justify-between items-center mb-6">
            <div>
              <h2 className="text-2xl font-bold text-slate-800 dark:text-cyan-50">Select a Database</h2>
              <p className="text-sm text-slate-500 dark:text-cyan-100/60 mt-1">
                Choose a data source to extract schema intelligence.
              </p>
            </div>
            <button
              onClick={onClose}
              className="p-2 rounded-full hover:bg-slate-200 dark:hover:bg-slate-800 text-slate-500 dark:text-slate-400 transition-colors"
            >
              <X className="w-6 h-6" />
            </button>
          </div>

          <div className="relative">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
            <input
              type="text"
              placeholder="Search databases..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full h-12 pl-12 pr-4 bg-white dark:bg-[#081120] border border-slate-200 dark:border-slate-700 rounded-xl focus:outline-none focus:ring-2 focus:ring-cyan-500 text-slate-900 dark:text-slate-100 placeholder-slate-400 transition-all"
            />
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-8 bg-transparent">
          {filteredDatabases.length === 0 ? (
            <div className="text-center py-12 text-slate-500 dark:text-slate-400">
              No databases found matching "{searchTerm}"
            </div>
          ) : (
            categories.map((category) => (
              <div key={category}>
                <h3 className="text-sm font-semibold text-slate-500 dark:text-cyan-100/50 uppercase tracking-wider mb-4">
                  {category}
                </h3>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
                  {filteredDatabases
                    .filter((db) => db.category === category)
                    .map((db) => (
                      <button
                        key={db.id}
                        onClick={() => {
                          onSelect(db);
                          onClose();
                        }}
                        className="group flex flex-col items-center justify-center p-6 bg-slate-50 dark:bg-[#0F172A]/80 border border-slate-200 dark:border-slate-800 rounded-2xl hover:border-cyan-500 dark:hover:border-cyan-500/50 hover:shadow-[0_0_20px_rgba(0,229,255,0.1)] transition-all duration-300"
                      >
                        <div className="mb-4 transform group-hover:scale-110 transition-transform duration-300">
                          {db.icon}
                        </div>
                        <span className="font-medium text-slate-800 dark:text-cyan-50 text-sm">
                          {db.name}
                        </span>
                      </button>
                    ))}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};
