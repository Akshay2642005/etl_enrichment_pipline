// Type definitions for Normalized Schema
export interface NormalizedColumn {
  columnName: string;
  dataType: string;
  nullable: boolean;
  isPrimaryKey: boolean;
  isForeignKey: boolean;
  description?: string;
  semanticType?: string;
  default?: string;
  unique?: boolean;
}

export interface NormalizedConstraint {
  name: string;
  type: string; // 'PRIMARY KEY', 'FOREIGN KEY', 'UNIQUE', 'CHECK'
  columnName: string;
}

export interface NormalizedRelationship {
  name: string;
  childTable: string;
  childColumn: string;
  parentTable: string;
  parentColumn: string;
}

export interface NormalizedTable {
  tableName: string;
  description?: string;
  columns: NormalizedColumn[];
  constraints: NormalizedConstraint[];
  relationships: NormalizedRelationship[];
  // Back-references (calculated)
  referencedBy: NormalizedRelationship[];
}

export interface NormalizedView {
  viewName: string;
  definition: string;
  columns: NormalizedColumn[];
}

export interface QualityMetrics {
  overallScore: string | number;
  completeness: string | number;
  relationships: string | number;
  naming: string | number;
  documentation: string | number;
  normalization: string | number;
}

export interface NormalizedSchema {
  databaseType: string;
  schemaName: string;
  tables: NormalizedTable[];
  views: NormalizedView[];
  globalRelationships: NormalizedRelationship[];
  metrics: QualityMetrics;
  timestamp: string;
}

export function normalizeSchema(rawJson: any): NormalizedSchema {
  // Check if it's enriched (has 'metadata' block at root and top-level 'relationships' as human string)
  const isEnriched = !!(rawJson.metadata && rawJson.tables && !rawJson.database_type);
  
  // Extract base info
  const databaseType = isEnriched ? (rawJson.metadata?.database_type || 'unknown') : (rawJson.database_type || 'unknown');
  const schemaName = isEnriched ? (rawJson.metadata?.schema || 'public') : (rawJson.schema || 'public');
  const timestamp = new Date().toISOString(); // Fallback if not in JSON
  
  // Extract Quality Metrics
  // Since backend doesn't explicitly provide these exact scores yet, we look for them or fallback to 'N/A'
  const qualityData = rawJson.metadata?.quality_scores || {};
  const metrics: QualityMetrics = {
    overallScore: qualityData.overall || 'N/A',
    completeness: qualityData.completeness || 'N/A',
    relationships: qualityData.relationships || 'N/A',
    naming: qualityData.naming || 'N/A',
    documentation: qualityData.documentation || 'N/A',
    normalization: qualityData.normalization || 'N/A',
  };

  const tables: NormalizedTable[] = [];
  const views: NormalizedView[] = [];
  const globalRelationships: NormalizedRelationship[] = [];

  // Parse Raw Output (from extraction_agent.py)
  if (!isEnriched) {
    (rawJson.tables || []).forEach((t: any) => {
      const constraints: NormalizedConstraint[] = (t.constraints || []).map((c: any) => ({
        name: c.constraint_name,
        type: c.constraint_type,
        columnName: c.column_name || c.column
      }));

      const relationships: NormalizedRelationship[] = (t.relationships || []).map((r: any) => {
        const rel = {
          name: r.constraint_name || `fk_${t.table_name}_${r.child_column}`,
          childTable: t.table_name,
          childColumn: r.child_column,
          parentTable: r.parent_table,
          parentColumn: r.parent_column
        };
        globalRelationships.push(rel);
        return rel;
      });

      const columns: NormalizedColumn[] = (t.columns || []).map((c: any) => ({
        columnName: c.column_name,
        dataType: c.data_type,
        nullable: c.nullable ?? true,
        isPrimaryKey: constraints.some(cons => cons.type === 'PRIMARY KEY' && cons.columnName === c.column_name),
        isForeignKey: constraints.some(cons => cons.type === 'FOREIGN KEY' && cons.columnName === c.column_name),
      }));

      tables.push({
        tableName: t.table_name,
        columns,
        constraints,
        relationships,
        referencedBy: []
      });
    });

    (rawJson.views || []).forEach((v: any) => {
      views.push({
        viewName: v.view_name,
        definition: v.definition || v.sql || '',
        columns: (v.columns || []).map((c: any) => ({
          columnName: c.column_name,
          dataType: c.data_type,
          nullable: c.nullable ?? true,
          isPrimaryKey: false,
          isForeignKey: false
        }))
      });
    });
  } 
  // Parse Enriched Output (from pipeline.py)
  else {
    // Pipeline outputs relationships as: { "name": "...", "description": "...", "child_table": "...", "parent_table": "..." }
    (rawJson.relationships || []).forEach((r: any) => {
      if (r.child_table && r.parent_table) {
        globalRelationships.push({
          name: r.name,
          childTable: r.child_table,
          childColumn: r.child_column || '',
          parentTable: r.parent_table,
          parentColumn: r.parent_column || ''
        });
      } else if (r.description && r.description.includes(' \u2192 ')) {
        const [child, parent] = r.description.split(' \u2192 ');
        const [childTable, childCol] = child.split('.');
        const [parentTable, parentCol] = parent.split('.');
        globalRelationships.push({
          name: r.name,
          childTable,
          childColumn: childCol,
          parentTable,
          parentColumn: parentCol
        });
      }
    });

    (rawJson.tables || []).forEach((t: any) => {
      const relationships = globalRelationships.filter(rel => rel.childTable === t.table_name);
      
      const columns: NormalizedColumn[] = (t.columns || []).map((c: any) => ({
        columnName: c.column_name,
        dataType: c.data_type,
        nullable: c.is_nullable ?? true,
        isPrimaryKey: c.is_primary_key || false,
        isForeignKey: relationships.some(rel => rel.childColumn === c.column_name),
        description: c.description,
        semanticType: c.semantic_type
      }));

      // We reconstruct basic constraints from flags
      const constraints: NormalizedConstraint[] = [];
      columns.forEach(c => {
        if (c.isPrimaryKey) constraints.push({ name: `pk_${t.table_name}_${c.columnName}`, type: 'PRIMARY KEY', columnName: c.columnName });
        if (c.isForeignKey) constraints.push({ name: `fk_${t.table_name}_${c.columnName}`, type: 'FOREIGN KEY', columnName: c.columnName });
      });

      tables.push({
        tableName: t.table_name,
        description: t.description,
        columns,
        constraints,
        relationships,
        referencedBy: []
      });
    });

    (rawJson.views || []).forEach((v: any) => {
      views.push({
        viewName: v.view_name,
        definition: v.definition || '',
        columns: (v.columns || []).map((c: any) => ({
          columnName: c.column_name,
          dataType: c.data_type,
          nullable: c.is_nullable ?? true,
          isPrimaryKey: false,
          isForeignKey: false
        }))
      });
    });
  }

  // Calculate referencedBy (inbound relations) for all tables
  tables.forEach(t => {
    t.referencedBy = globalRelationships.filter(rel => rel.parentTable === t.tableName);
  });

  return {
    databaseType,
    schemaName,
    tables,
    views,
    globalRelationships,
    metrics,
    timestamp
  };
}
