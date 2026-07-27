import { S3Client } from "@aws-sdk/client-s3";
import { GetObjectCommand } from "@aws-sdk/client-s3";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";

// Singleton pattern → only one client is created and reused
let s3Client: S3Client;
export function getS3Client() {
  if (!s3Client) {
    s3Client = new S3Client({
      region: process.env.AWS_REGION || "ap-south-1",
      credentials: {
        accessKeyId: process.env.AWS_ACCESS_KEY_ID!,
        secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY!,
      },
    });
  }
  return s3Client;
}

// Test function to verify S3 URI parsing
export function testS3UriParsing(s3Uri: string) {
  // console.log('=== S3 URI Parsing Test ===');
  // console.log('Input:', s3Uri);
  
  try {
    const { bucket, key } = parseS3Uri(s3Uri);
    // console.log('Parsed bucket:', bucket);
    // console.log('Parsed key:', key);
    // console.log('Expected Object URL:', `https://${bucket}.s3.ap-south-1.amazonaws.com/${key}`);
    return { bucket, key, success: true };
  } catch (error) {
    console.error('Parsing failed:', error);
    return { bucket: '', key: '', success: false, error };
  }
}

function parseS3Uri(s3Uri: string): { bucket: string; key: string } {
  // console.log('parseS3Uri: Input URI:', s3Uri);
  
  if (!s3Uri) {
    throw new Error('S3 URI is required');
  }
  
  // Handle s3:// format
  if (s3Uri.startsWith('s3://')) {
    // console.log('parseS3Uri: Detected s3:// format');
    const withoutProtocol = s3Uri.substring(5); // Remove 's3://'
    // console.log('parseS3Uri: Without protocol:', withoutProtocol);
    const firstSlashIndex = withoutProtocol.indexOf('/');
    if (firstSlashIndex === -1) {
      throw new Error('Invalid S3 URI format');
    }
    const result = {
      bucket: withoutProtocol.substring(0, firstSlashIndex),
      key: withoutProtocol.substring(firstSlashIndex + 1)
    };
    // console.log('parseS3Uri: Parsed result:', result);
    return result;
  }
  
  // Handle legacy format bucket-name/path/to/file
  // console.log('parseS3Uri: Detected legacy format');
  const firstSlashIndex = s3Uri.indexOf('/');
  if (firstSlashIndex === -1) {
    throw new Error('Invalid S3 URI format');
  }
  const result = {
    bucket: s3Uri.substring(0, firstSlashIndex),
    key: s3Uri.substring(firstSlashIndex + 1)
  };
  // console.log('parseS3Uri: Parsed result:', result);
  return result;
}

export async function getSignedAudioUrl(url: string, expiresIn = 3600) {
  if (!url) return '';
  
  try {
    const { bucket, key } = parseS3Uri(url);
    const client = getS3Client();
    const command = new GetObjectCommand({
      Bucket: bucket,
      Key: key,
    });

    return await getSignedUrl(client, command, { expiresIn });
  } catch (error) {
    console.error('Error generating signed audio URL:', error);
    return '';
  }
}

export async function getSignedImageUrl(url: string, expiresIn = 3600) {
  if (!url) {
    // console.log('getSignedImageUrl: Empty URL provided');
    return '';
  }
  
  // Only sign S3 URIs (backup images). Return regular HTTPS/HTTP URLs as-is
  if (!url.startsWith('s3://')) {
    // Regular image URL (HTTPS/HTTP) - return as-is without signing
    return url;
  }
  
  // console.log('getSignedImageUrl: Processing S3 URI:', url);
  
  try {
    const { bucket, key } = parseS3Uri(url);
    // console.log('getSignedImageUrl: Parsed - Bucket:', bucket, 'Key:', key);
    
    // Check AWS credentials
    if (!process.env.AWS_ACCESS_KEY_ID || !process.env.AWS_SECRET_ACCESS_KEY) {
      console.error('getSignedImageUrl: Missing AWS credentials');
      return '';
    }
    
    const client = getS3Client();
    // console.log('getSignedImageUrl: S3 client created, region:', process.env.AWS_REGION || "ap-south-1");
    
    const command = new GetObjectCommand({
      Bucket: bucket,
      Key: key,
    });

    // console.log('getSignedImageUrl: Generating signed URL...');
    const signedUrl = await getSignedUrl(client, command, { expiresIn });
    // console.log('getSignedImageUrl: Generated signed URL length:', signedUrl.length);
    // console.log('getSignedImageUrl: Generated signed URL (first 100 chars):', signedUrl.substring(0, 100));
    
    return signedUrl;
  } catch (error) {
    console.error('Error generating signed image URL for URL:', url);
    console.error('Error details:', error);
    if (error instanceof Error) {
      console.error('Error message:', error.message);
      console.error('Error stack:', error.stack);
    }
    return '';
  }
}

