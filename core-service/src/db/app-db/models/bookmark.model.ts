import { DataTypes, Model, Sequelize } from 'sequelize';
import type { AppDbModels } from '../index';

export class Bookmark extends Model {
    declare id: string;
    declare user_id: string;
    declare event_id: string;
    declare createdAt: Date;
}

export const BookmarkModel = {
    define: (sequelize: Sequelize) => {
        Bookmark.init(
            {
                id: {
                    type: DataTypes.UUID,
                    defaultValue: DataTypes.UUIDV4,
                    primaryKey: true,
                },

                user_id: {
                    type: DataTypes.UUID,
                    allowNull: false,
                },

                event_id: {
                    type: DataTypes.UUID,
                    allowNull: false,
                },

                createdAt: {
                    type: DataTypes.DATE,
                    defaultValue: DataTypes.NOW,
                },
            },
            {
                sequelize,
                modelName: 'Bookmark',
                tableName: 'bookmarks',
                timestamps: false,
            }
        );

        return Bookmark;
    },

    createAssociations: (models: AppDbModels) => {
        Bookmark.belongsTo(models.User, { foreignKey: 'user_id' });
        Bookmark.belongsTo(models.Event, { foreignKey: 'event_id' });
    },
};
