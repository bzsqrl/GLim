#pragma once
#include <FFGLSDK.h>
#include <string>

class FFMakerPlugin : public ffglqs::Plugin
{
public:
	FFMakerPlugin();
	~FFMakerPlugin();

	FFResult InitGL( const FFGLViewportStruct* vp ) override;
	FFResult ProcessOpenGL( ProcessOpenGLStruct* pGL ) override;
	FFResult DeInitGL() override;

	const char* GetShortName() override
	{
		static const char* sname = "FFMP";
		return sname;
	}

private:
	ffglex::FFGLShader shader;
	ffglex::FFGLScreenQuad quad;

	float iTime = 0.0f;
	float iTimeDelta = 0.0f;
	int iFrame = 0;
};
