export interface Column {
  column_name: string;
  data_type: string;
  nullable: boolean;
}

export interface Constraint {
  constraint_name: string;
  constraint_type: string;
  column_name: string;
}

export interface Relationship {
  child_column: string;
  parent_table: string;
  parent_column: string;
}

export interface Table {
  table_name: string;
  columns: Column[];
  constraints?: Constraint[];
  relationships?: Relationship[];
}

export interface View {
  view_name: string;
  columns: Column[];
  definition: string;
}

export interface Database {
  database_type: string;
  schema: string;
  tables: Table[];
  views?: View[];
}
