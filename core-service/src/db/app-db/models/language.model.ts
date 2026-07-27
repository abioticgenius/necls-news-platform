import { DataTypes, Model, Sequelize } from 'sequelize';
import type { AppDbModels } from '../index';

export class Language extends Model {
  declare id: string; 
  declare name: string;
}

export const LanguageModel = {
  define: (sequelize: Sequelize) => {
    Language.init({
      id: {
        type: DataTypes.TEXT,
        primaryKey: true,
      },
      name: {
        type: DataTypes.TEXT,
        allowNull: false,
      },
    }, {
      sequelize,
      modelName: 'Language',
      tableName: 'language',
      timestamps: false,
    });
    return Language;
  },
  createAssociations: (models: AppDbModels) => {
    Language.hasMany(models.LocalizedEventData, { foreignKey: 'language_id' });
    Language.hasMany(models.LocalizedEventSoFar, { foreignKey: 'language_id' });
    Language.hasMany(models.LocalizedEventAnalysis, { foreignKey: 'language_id' });
  }
}; 