import { DataTypes, Model, Sequelize } from 'sequelize';
import type { AppDbModels } from '../index';

export class CollectionSeoTag extends Model {
  declare id: string;
  declare collection_id: string;
  declare seo_tag_id: string;
  declare created_date: Date;
}

export const CollectionSeoTagModel = {
  define: (sequelize: Sequelize) => {
    CollectionSeoTag.init({
      id: {
        type: DataTypes.UUID,
        defaultValue: DataTypes.UUIDV4,
        primaryKey: true,
      },
      collection_id: {
        type: DataTypes.UUID,
        allowNull: false,
        references: {
          model: 'Collection',
          key: 'id',
        },
        onDelete: 'CASCADE',
      },
      seo_tag_id: {
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
    }, {
      sequelize,
      modelName: 'CollectionSeoTag',
      tableName: 'collection_seo_tag',
      timestamps: false,
      indexes: [
        {
          unique: true,
          fields: ['collection_id', 'seo_tag_id'],
          name: 'uq_collection_seo_tag_collection_tag',
        }
      ],
    });

    return CollectionSeoTag;
  },

  createAssociations: (models: AppDbModels) => {
    CollectionSeoTag.belongsTo(models.Collection, { foreignKey: 'collection_id' });
    CollectionSeoTag.belongsTo(models.SeoTag, { foreignKey: 'seo_tag_id' });
  }
};
