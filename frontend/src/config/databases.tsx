import React from 'react';
import { Database, FileCode, Server } from 'lucide-react';

export interface DatabaseConfig {
  id: string;
  name: string;
  category: 'Relational' | 'NoSQL' | 'Cloud Data Warehouse' | 'Embedded' | 'Other';
  defaultPort?: string;
  isPopular?: boolean;
  icon: React.ReactNode;
  isSqlUpload?: boolean;
}

// Simple inline SVG components for database logos to avoid external dependencies
const PostgresIcon = () => (
  <svg viewBox="0 0 100 100" className="w-8 h-8" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M50 10C27.9086 10 10 27.9086 10 50C10 72.0914 27.9086 90 50 90C72.0914 90 90 72.0914 90 50C90 27.9086 72.0914 10 50 10Z" fill="#336791"/>
    <path d="M43.7143 31.4286H62V40.5714H43.7143V31.4286ZM38 31.4286H40.2857V68.5714H38V31.4286Z" fill="white"/>
    <path d="M50 49.7143C56.2857 49.7143 62 53.1429 62 58.8571C62 64.5714 56.2857 68 50 68C43.7143 68 38 64.5714 38 58.8571C38 53.1429 43.7143 49.7143 50 49.7143Z" fill="white"/>
  </svg>
);

const MysqlIcon = () => (
  <svg viewBox="0 0 100 100" className="w-8 h-8" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M50 10C27.9086 10 10 27.9086 10 50C10 72.0914 27.9086 90 50 90C72.0914 90 90 72.0914 90 50C90 27.9086 72.0914 10 50 10Z" fill="#00758F"/>
    <path d="M25 65C25 65 35 75 50 75C65 75 75 65 75 65M35 45C35 45 40 55 50 55C60 55 65 45 65 45" stroke="white" strokeWidth="6" strokeLinecap="round"/>
    <circle cx="35" cy="35" r="5" fill="white"/>
    <circle cx="65" cy="35" r="5" fill="white"/>
  </svg>
);

const SqlServerIcon = () => (
  <svg viewBox="0 0 100 100" className="w-8 h-8" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M10 20L50 10L90 20V80L50 90L10 80V20Z" fill="#CC292B"/>
    <path d="M30 40H70V50H30V40ZM30 60H70V70H30V60Z" fill="white"/>
  </svg>
);

const OracleIcon = () => (
  <svg viewBox="0 0 100 100" className="w-8 h-8" fill="none" xmlns="http://www.w3.org/2000/svg">
    <rect width="100" height="100" rx="20" fill="#F80000"/>
    <path d="M25 35H75V45H25V35ZM25 55H75V65H25V55Z" fill="white"/>
  </svg>
);

const SqliteIcon = () => (
  <svg viewBox="0 0 100 100" className="w-8 h-8" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M50 10L15 30V70L50 90L85 70V30L50 10Z" fill="#003B57"/>
    <ellipse cx="50" cy="50" rx="15" ry="10" fill="white"/>
    <path d="M35 50V60C35 65 50 70 50 70C50 70 65 65 65 60V50" stroke="white" strokeWidth="5"/>
  </svg>
);

const MariaDbIcon = () => (
  <svg viewBox="0 0 100 100" className="w-8 h-8" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M50 10C27.9086 10 10 27.9086 10 50C10 72.0914 27.9086 90 50 90C72.0914 90 90 72.0914 90 50C90 27.9086 72.0914 10 50 10Z" fill="#003545"/>
    <path d="M30 40H40V60H30V40ZM60 40H70V60H60V40Z" fill="white"/>
    <path d="M40 50L50 40L60 50L50 60L40 50Z" fill="white"/>
  </svg>
);


export const DATABASE_LIST: DatabaseConfig[] = [
  {
    id: 'postgres',
    name: 'PostgreSQL',
    category: 'Relational',
    defaultPort: '5432',
    isPopular: true,
    icon: <PostgresIcon />
  },
  {
    id: 'mysql',
    name: 'MySQL',
    category: 'Relational',
    defaultPort: '3306',
    isPopular: true,
    icon: <MysqlIcon />
  },
  {
    id: 'sqlserver',
    name: 'SQL Server',
    category: 'Relational',
    defaultPort: '1433',
    isPopular: true,
    icon: <SqlServerIcon />
  },
  {
    id: 'oracle',
    name: 'Oracle',
    category: 'Relational',
    defaultPort: '1521',
    isPopular: true,
    icon: <OracleIcon />
  },
  {
    id: 'mariadb',
    name: 'MariaDB',
    category: 'Relational',
    defaultPort: '3306',
    isPopular: true,
    icon: <MariaDbIcon />
  },
  {
    id: 'sqlite',
    name: 'SQLite',
    category: 'Embedded',
    isPopular: true,
    icon: <SqliteIcon />
  },
  {
    id: 'sql',
    name: 'SQL Upload',
    category: 'Other',
    isPopular: true,
    isSqlUpload: true,
    icon: <FileCode className="w-8 h-8 text-cyan-500" />
  },
  // Future scalable additions
  {
    id: 'mongodb',
    name: 'MongoDB',
    category: 'NoSQL',
    defaultPort: '27017',
    icon: <Database className="w-8 h-8 text-green-500" />
  },
  {
    id: 'redis',
    name: 'Redis',
    category: 'NoSQL',
    defaultPort: '6379',
    icon: <Server className="w-8 h-8 text-red-500" />
  },
  {
    id: 'snowflake',
    name: 'Snowflake',
    category: 'Cloud Data Warehouse',
    icon: <Database className="w-8 h-8 text-blue-400" />
  },
  {
    id: 'bigquery',
    name: 'BigQuery',
    category: 'Cloud Data Warehouse',
    icon: <Database className="w-8 h-8 text-blue-600" />
  }
];
