import { Sequelize } from 'sequelize';
import { CategoryModel } from './models/category.model';
import { EventModel } from './models/event.model';
import { EventAnalysisModel } from './models/eventanalysis.model';
import { EventSoFarModel } from './models/eventsofar.model';
import { SourceModel } from './models/source.model';
import { LocalizedEventDataModel } from './models/localizedeventdata.model';
import { LocalizedEventSoFarModel } from './models/localizedeventsofar.model';
import { LocalizedEventAnalysisModel } from './models/localizedeventanalysis.model';
import { LanguageModel } from './models/language.model';
import { LogosModel } from './models/logos.model';
import { UserModel } from './models/user.model';
import { CollectionModel } from './models/collection.model';
import { BookmarkModel } from './models/bookmark.model';
import { SeoTagModel } from './models/seotag.model';
import { SeoTagRelationModel } from './models/seotagrelation.model';
import { EventSeoTagModel } from './models/eventseotag.model';
import { CollectionSeoTagModel } from './models/collectionseotag.model';
import { EventFaqModel } from './models/eventfaq.model';
import { AssistantChunkModel } from './models/assistantchunk.model';
import { AppConfigModel } from './models/appconfig.model';
import { UserDevice, UserDeviceModel } from './models/userdevice.model';

export type AppDbModels = {
    Category: ReturnType<typeof CategoryModel.define>;
    Event: ReturnType<typeof EventModel.define>;
    EventAnalysis: ReturnType<typeof EventAnalysisModel.define>;
    EventSoFar: ReturnType<typeof EventSoFarModel.define>;
    Source: ReturnType<typeof SourceModel.define>;
    LocalizedEventData: ReturnType<typeof LocalizedEventDataModel.define>;
    LocalizedEventSoFar: ReturnType<typeof LocalizedEventSoFarModel.define>;
    LocalizedEventAnalysis: ReturnType<typeof LocalizedEventAnalysisModel.define>;
    Language: ReturnType<typeof LanguageModel.define>;
    Logos: ReturnType<typeof LogosModel.define>;
    SeoTag: ReturnType<typeof SeoTagModel.define>;
    SeoTagRelation: ReturnType<typeof SeoTagRelationModel.define>;
    EventSeoTag: ReturnType<typeof EventSeoTagModel.define>;
    User: ReturnType<typeof UserModel.define>;
    UserDevice: ReturnType<typeof UserDeviceModel.define>;
    Collection: ReturnType<typeof CollectionModel.define>;
    CollectionSeoTag: ReturnType<typeof CollectionSeoTagModel.define>;
    Bookmark: ReturnType<typeof BookmarkModel.define>;
    AssistantChunk: ReturnType<typeof AssistantChunkModel.define>;
    EventFaq: ReturnType<typeof EventFaqModel.define>;
    AppConfig: ReturnType<typeof AppConfigModel.define>;
};

export async function initAppDb() {
    console.log('Initializing App Database...');
    console.log('DB Config:', {
        host: process.env.APP_DB_HOST,
        port: process.env.APP_DB_PORT,
        database: process.env.APP_DB_NAME,
        user: process.env.APP_DB_USER
    });

    const sequelize = new Sequelize(
        process.env.APP_DB_NAME!,
        process.env.APP_DB_USER!,
        process.env.APP_DB_PASSWORD!,
        {
            host: process.env.APP_DB_HOST!,
            port: Number(process.env.APP_DB_PORT!),
            dialect: 'postgres',
            dialectOptions: {
                connectTimeout: 30000,
                ...(process.env.APP_DB_SSL !== 'false' && {
                    ssl: {
                        require: true,
                        rejectUnauthorized: false,
                    }
                }),
            },
            pool: {
                max: 5,
                min: 0,
                acquire: 30000,
                idle: 10000
            }
        }
    );

    console.log('Defining models...');
    const models = {
        Category: CategoryModel.define(sequelize),
        Event: EventModel.define(sequelize),
        EventAnalysis: EventAnalysisModel.define(sequelize),
        EventSoFar: EventSoFarModel.define(sequelize),
        Source: SourceModel.define(sequelize),
        LocalizedEventData: LocalizedEventDataModel.define(sequelize),
        LocalizedEventSoFar: LocalizedEventSoFarModel.define(sequelize),
        LocalizedEventAnalysis: LocalizedEventAnalysisModel.define(sequelize),
        Language: LanguageModel.define(sequelize),
        Logos: LogosModel.define(sequelize),
        SeoTag: SeoTagModel.define(sequelize),
        SeoTagRelation: SeoTagRelationModel.define(sequelize),
        EventSeoTag: EventSeoTagModel.define(sequelize),
        User: UserModel.define(sequelize),
        UserDevice: UserDeviceModel.define(sequelize),
        Collection: CollectionModel.define(sequelize),
        CollectionSeoTag: CollectionSeoTagModel.define(sequelize),
        Bookmark: BookmarkModel.define(sequelize),
        AssistantChunk: AssistantChunkModel.define(sequelize),
        EventFaq: EventFaqModel.define(sequelize),
        AppConfig: AppConfigModel.define(sequelize),
    };

    console.log('Creating associations...');
    CategoryModel.createAssociations(models);
    EventModel.createAssociations(models);
    EventAnalysisModel.createAssociations(models);
    EventSoFarModel.createAssociations(models);
    SourceModel.createAssociations(models);
    LocalizedEventDataModel.createAssociations(models);
    LocalizedEventSoFarModel.createAssociations(models);
    LocalizedEventAnalysisModel.createAssociations(models);
    LanguageModel.createAssociations(models);
    LogosModel.createAssociations(models);
    CollectionModel.createAssociations(models);
    BookmarkModel.createAssociations(models);
    SeoTagModel.createAssociations(models);
    SeoTagRelationModel.createAssociations(models);
    EventSeoTagModel.createAssociations(models);
    CollectionSeoTagModel.createAssociations(models);
    AssistantChunkModel.createAssociations(models);
    EventFaqModel.createAssociations(models);
    AppConfigModel.createAssociations(models);
    UserModel.createAssociations(models);
    UserDeviceModel.createAssociations(models);

    console.log('Authenticating database connection...');
    await sequelize.authenticate();
    console.log('Syncing database...');

    // Sync SeoTag first (before dependent tables like EventSeoTag and CollectionSeoTag)
    // Use drop:false so Sequelize never removes migration-managed columns
    // (embedding vector(128), vector_updated_at) that are not declared in the model.
    try {
        await models.SeoTag.sync({ alter: { drop: false } });
        console.log('SeoTag table synced');
    } catch (error: any) {
        console.warn(`Warning syncing SeoTag:`, error.message);
        try {
            await models.SeoTag.sync({ alter: false });
            console.log('SeoTag table exists (using existing schema)');
        } catch (error2: any) {
            console.log('SeoTag table sync skipped:', error2.message);
        }
    }

    // Sync Logos before Source (Source depends on Logos)
    try {
        await models.Logos.sync({ alter: true });
        console.log('Logos table synced');
    } catch (error: any) {
        console.warn(`Warning syncing Logos:`, error.message);
    }

    // Sync Language before LocalizedEventData, LocalizedEventSoFar, LocalizedEventAnalysis
    try {
        await models.Language.sync({ alter: true });
        console.log('Language table synced');
    } catch (error: any) {
        console.warn(`Warning syncing Language:`, error.message);
    }

    // Sync models individually to skip tables with custom types
    // AssistantChunk: has vector type (pgvector extension)
    const modelsToSync = Object.entries(models).filter(([name]) =>
        name !== 'SeoTag' && name !== 'AssistantChunk' && name !== 'Logos' && name !== 'Language'
    );

    for (const [modelName, model] of modelsToSync) {
        try {
            await (model as any).sync({ alter: true });
        } catch (error: any) {
            console.warn(`Warning syncing ${modelName}:`, error.message);
        }
    }

    // Sync AssistantChunk without alter to avoid type conflicts
    // This table uses custom database types that Sequelize can't manage
    try {
        await models.AssistantChunk.sync({ alter: false });
        console.log('AssistantChunk table exists (using existing vector type)');
    } catch (error: any) {
        console.log('AssistantChunk table sync skipped:', error.message);
    }

    // Run seeds after database sync
    const { runSeeds } = await import('../seeds');
    await runSeeds();

    console.log('App Database initialized successfully!');
    return { sequelize, models };
}
