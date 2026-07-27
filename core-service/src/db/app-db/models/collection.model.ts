// models/Collection.ts
import { DataTypes, Model, Sequelize } from 'sequelize';
import type { AppDbModels } from '../index';

export class Collection extends Model {
    declare id: string;
    declare user_id: string;
    declare title: string;
    declare description: string | null;
    declare is_thinko: boolean;
    declare is_public: boolean;
    declare tags: string | null;        // comma-separated tags like "sports,business,world"
    declare and_tag_id: string | null;  // optional place-tag AND filter (applied against all orTags)
    declare collection_rule: object | null;  // AND/OR rule for article filtering (stored for ThinkO collections)

    declare createdAt: Date;
    declare updatedAt: Date;
}

export const CollectionModel = {
    define: (sequelize: Sequelize) => {
        Collection.init(
            {
                id: {
                    type: DataTypes.UUID,
                    defaultValue: DataTypes.UUIDV4,
                    primaryKey: true,
                },

                user_id: {
                    type: DataTypes.UUID,
                    allowNull: true,
                },

                title: {
                    type: DataTypes.STRING(120),
                    allowNull: false,
                },

                description: {
                    type: DataTypes.TEXT,
                    allowNull: true,
                },

                is_thinko: {
                    type: DataTypes.BOOLEAN,
                    defaultValue: false,
                },
                is_public: {
                    type: DataTypes.BOOLEAN,
                    defaultValue: false,
                },
                and_tag_id: {
                    type: DataTypes.UUID,
                    allowNull: true,
                },
                collection_rule: {
                    type: DataTypes.JSONB,
                    allowNull: true,
                },
                createdAt: DataTypes.DATE,
                updatedAt: DataTypes.DATE,
            },
            {
                sequelize,
                modelName: 'Collection',
                tableName: 'collection',
                timestamps: true,
            }
        );

        return Collection;
    },

    createAssociations: (models: AppDbModels) => {
        Collection.hasMany(models.CollectionSeoTag, { foreignKey: 'collection_id', as: 'CollectionSeoTags' });
        Collection.belongsTo(models.User, { foreignKey: 'user_id' });
        Collection.belongsToMany(models.SeoTag, {through: models.CollectionSeoTag, foreignKey: 'collection_id', otherKey: 'seo_tag_id', as: 'SeoTags'});
        Collection.belongsTo(models.SeoTag, { foreignKey: 'and_tag_id', as: 'AndTag' });
    },
};
