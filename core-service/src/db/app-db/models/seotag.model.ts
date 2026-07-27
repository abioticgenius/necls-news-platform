import { DataTypes, Model, Sequelize } from 'sequelize';
import type { AppDbModels } from '../index';

// Custom DataType so Sequelize knows the column exists (and never drops it)
// without trying to convert it from vector(128) to real[].
class PgVector extends (DataTypes.ABSTRACT as any) {
  toSql() { return 'vector(128)'; }
}
const VECTOR_128 = new PgVector();

export class SeoTag extends Model {
  declare id: string;
  declare name: string; // Multi-word tags allowed (2-4 words), e.g., "Climate Change", "Economic Policy"
  declare type: string;
  declare created_date: Date;
  declare embedding: number[] | null;
  declare vector_updated_at: Date | null;
}
const ALLOWED_TYPES = ['tag', 'Category', 'Sub Category', 'Core Event', 'Associated Event', 'Entity', 'Place', 'Impact'];
export const SeoTagModel = {
  define: (sequelize: Sequelize) => {
    SeoTag.init({
      id: {
        type: DataTypes.UUID,
        defaultValue: DataTypes.UUIDV4,
        primaryKey: true,
      },
      name: {
        type: DataTypes.TEXT,
        allowNull: false,
        // Note: unique constraint is on (name, type) combination at database level
        // Removing unique: true here to match database schema
        validate: {
          // Ensure tag is not empty
          notEmpty: true,
        },
      },
      type: {
        type: DataTypes.ENUM(...ALLOWED_TYPES),
        allowNull: false,
        defaultValue: 'tag',
        validate: {
          isIn: [ALLOWED_TYPES],
        },
      },
      created_date: {
        type: DataTypes.DATE,
        allowNull: false,
        defaultValue: Sequelize.fn('now'),
      },
      embedding: {
        type: VECTOR_128 as any,
        allowNull: true,
      },
      vector_updated_at: {
        type: DataTypes.DATE,
        allowNull: true,
      },
    }, {
      sequelize,
      modelName: 'SeoTag',
      tableName: 'seo_tag',
      timestamps: false,
      indexes: [
        {
          unique: true,
          fields: ['name', 'type'],
          name: 'uq_seo_tag_name_type',
        }]
    });
    return SeoTag;
  },
  createAssociations: (models: AppDbModels) => {

    SeoTag.hasMany(models.EventSeoTag, { foreignKey: 'seo_tag_id', as: 'EventSeoTags' });
    SeoTag.hasMany(models.CollectionSeoTag, { foreignKey: 'seo_tag_id', as: 'CollectionSeoTags' });
    SeoTag.belongsToMany(models.Event, { through: models.EventSeoTag, foreignKey: 'seo_tag_id', otherKey: 'event_id', as: 'Events', });
    SeoTag.belongsToMany(models.Collection, { through: models.CollectionSeoTag, foreignKey: 'seo_tag_id', otherKey: 'collection_id', as: 'Collections', });


    SeoTag.hasMany(models.SeoTagRelation, {
      foreignKey: 'parent_tag_id',
      as: 'ParentRelations', 
      constraints: false,
    });

    SeoTag.hasMany(models.SeoTagRelation, {
      foreignKey: 'child_tag_id',
      as: 'ChildRelationsions',
      constraints: false,
    });
  }
};

