import { DataTypes, Model, Sequelize } from 'sequelize';
import type { AppDbModels } from '../index';
import { ContentType, CONTENT_TYPE_VALUES } from '../../../types/ReqResTypes';

export class LocalizedEventAnalysis extends Model {
  declare id: string;
  declare language_id: string;
  declare event_analysis_id: string;
  declare content: object;
  declare contentType: ContentType;
}

export const LocalizedEventAnalysisModel = {
  define: (sequelize: Sequelize) => {
    LocalizedEventAnalysis.init({
      id: {
        type: DataTypes.UUID,
        defaultValue: DataTypes.UUIDV4,
        primaryKey: true,
      },
      language_id: {
        type: DataTypes.TEXT,
        allowNull: false,
      },
      event_analysis_id: {
        type: DataTypes.UUID,
        allowNull: false,
        references: {
          model: 'event_analysis',
          key: 'id',
        },
        onDelete: 'CASCADE',
      },
      content: {
        type: DataTypes.JSONB,
        allowNull: true,
      },
      contentType: {
        type: DataTypes.ENUM(...CONTENT_TYPE_VALUES),
        allowNull: true,
        field: 'content_type', // Map to database column
      },
    }, {
      sequelize,
      modelName: 'LocalizedEventAnalysis',
      tableName: 'localized_event_analysis',
      timestamps: false,
      indexes: [
        {
          unique: true,
          fields: ['event_analysis_id', 'language_id'],
          name: 'uq_lea_event_lang',
        },
      ],
    });
    return LocalizedEventAnalysis;
  },
  createAssociations: (models: AppDbModels) => {
    LocalizedEventAnalysis.belongsTo(models.EventAnalysis, { foreignKey: 'event_analysis_id' });
    LocalizedEventAnalysis.belongsTo(models.Language, { foreignKey: 'language_id' });
  }
};
