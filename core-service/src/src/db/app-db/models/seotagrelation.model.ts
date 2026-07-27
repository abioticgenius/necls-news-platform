import { DataTypes, Model, Sequelize } from 'sequelize';
import type { AppDbModels } from '../index';

export class SeoTagRelation extends Model {
  declare id: string;
  declare parent_tag_id: string;
  declare child_tag_id: string;
  declare created_date: Date;
}

export const SeoTagRelationModel = {
  define: (sequelize: Sequelize) => {
    SeoTagRelation.init(
      {
        id: {
          type: DataTypes.UUID,
          defaultValue: DataTypes.UUIDV4,
          primaryKey: true,
        },
        parent_tag_id: {
          type: DataTypes.UUID,
          allowNull: false,
          references: {
            model: 'seo_tag',
            key: 'id',
          },
          onDelete: 'CASCADE',
        },
        child_tag_id: {
          type: DataTypes.UUID,
          allowNull: false,
          references: {
            model: 'seo_tag',
            key: 'id',
          },
          onDelete: 'CASCADE',
        },
        created_date: {
          type: DataTypes.DATE,
          allowNull: false,
          defaultValue: Sequelize.fn('now'),
        },
      },
      {
        sequelize,
        modelName: 'SeoTagRelation',
        tableName: 'seo_tag_relation',
        timestamps: false,
        indexes: [
          {
            unique: true,
            fields: ['parent_tag_id', 'child_tag_id'],
            name: 'uq_seo_tag_relation_unique',
          },
          {
            fields: ['parent_tag_id'],
            name: 'idx_seo_tag_relation_parent',
          },
          {
            fields: ['child_tag_id'],
            name: 'idx_seo_tag_relation_child',
          },
        ],
      }
    );

    return SeoTagRelation;
  },

  createAssociations: (models: AppDbModels) => {
    SeoTagRelation.belongsTo(models.SeoTag, {
      foreignKey: 'parent_tag_id',
      as: 'ParentTag',
    });
    
    SeoTagRelation.belongsTo(models.SeoTag, {
      foreignKey: 'child_tag_id',
      as: 'ChildTag',
    });
    
  },
};
